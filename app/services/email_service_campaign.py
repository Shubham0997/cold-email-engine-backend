import logging
from datetime import datetime
from app.domain.models import Campaign, CampaignRecipient, Email, db
from app.repository.campaign_repository import CampaignRepository
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

class CampaignService:
    def __init__(self, repository: CampaignRepository, email_service: EmailService):
        self.repository = repository
        self.email_service = email_service

    def create_campaign(self, name: str, subject: str, body: str, recipient_emails: list[str], user_id: str = None) -> Campaign:
        if self.repository.get_by_name(name, user_id=user_id):
            raise ValueError(f"A campaign with the name '{name}' already exists.")

        campaign = Campaign(
            name=name,
            subject=subject,
            body=body,
            status="DRAFT",
            user_id=user_id
        )
        self.repository.create(campaign)
        
        # Bulk insert recipients
        recipients = [
            CampaignRecipient(campaign_id=campaign.id, email=email, status="PENDING")
            for email in recipient_emails
        ]
        db.session.add_all(recipients)
        db.session.commit()
            
        return campaign

    def start_campaign(self, campaign_id: str, user_id: str = None):
        campaign = self.repository.get_by_id(campaign_id)
        if not campaign or campaign.status == "SENDING":
            return
        
        # Authorization check: ensure campaign belongs to this user
        if user_id and campaign.user_id and campaign.user_id != user_id:
            raise ValueError("You do not have permission to start this campaign.")
        
        campaign.status = "SENDING"
        self.repository.update_campaign_status(campaign.id, "SENDING")
        
        logger.info(f"Starting campaign: {campaign.name} ({campaign.id})")
        
        with self.email_service.smtp_connection(campaign.user_id) as server:
            for recipient in campaign.recipients:
                if recipient.status != "PENDING":
                    logger.debug(f"Skipping recipient {recipient.email} (status: {recipient.status})")
                    continue
                
                try:
                    # Basic variable substitution: {{email}}
                    personalized_subject = campaign.subject.replace("{{email}}", recipient.email)
                    personalized_body = campaign.body.replace("{{email}}", recipient.email)
                    
                    # 1. Register the email record immediately to get the tracking ID
                    email_record = self.email_service.register_email(
                        recipient=recipient.email,
                        message=personalized_body,
                        subject=personalized_subject,
                        user_id=campaign.user_id  # Inherit user_id from the campaign
                    )
                    
                    # 2. Link the recipient to the tracking ID
                    recipient.email_id = email_record.id
                    
                    logger.info(f"Sending campaign email to {recipient.email} (ID: {email_record.id})...")
                    
                    # 3. Send via SMTP (the long-running part) - Pass the server for reuse!
                    result = self.email_service.send_email_by_record(email_record, server=server)
                    
                    if result:
                        recipient.status = result.status
                    
                except Exception as e:
                    logger.error(f"Failed to send campaign email to {recipient.email}: {e}")
                    recipient.status = "FAILED"
        
        campaign.status = "COMPLETED"
        # One final commit for the whole campaign batch
        db.session.commit()
        logger.info(f"Campaign completed: {campaign.name}")

    def get_all_campaigns(self, user_id: str = None) -> list[Campaign]:
        return self.repository.get_all(user_id=user_id)

    def get_campaign_details(self, campaign_id: str, user_id: str = None) -> dict | None:
        campaign = self.repository.get_by_id(campaign_id)
        if not campaign:
            return None
        
        # Authorization check
        if user_id and campaign.user_id and campaign.user_id != user_id:
            return None
        
        return {
            "campaign": campaign.to_dict(),
            "recipients": [r.to_dict() for r in campaign.recipients]
        }

    def update_campaign(self, campaign_id: str, name: str, subject: str, body: str, recipient_emails: list[str], user_id: str = None) -> Campaign | None:
        campaign = self.repository.get_by_id(campaign_id)
        if not campaign:
            return None
        
        # Authorization check
        if user_id and campaign.user_id and campaign.user_id != user_id:
            return None
        
        # Check if new name is taken by another campaign (scoped to user)
        existing = self.repository.get_by_name(name, user_id=user_id)
        if existing and existing.id != campaign_id:
            raise ValueError(f"A campaign with the name '{name}' already exists.")

        campaign.name = name
        campaign.subject = subject
        campaign.body = body
        
        # If campaign is in DRAFT or COMPLETED, we can refresh recipients
        if campaign.status in ["DRAFT", "COMPLETED"]:
            self.repository.delete_recipients_by_campaign_id(campaign_id)
            for email in recipient_emails:
                recipient = CampaignRecipient(
                    campaign_id=campaign.id,
                    email=email,
                    status="PENDING"
                )
                self.repository.add_recipient(recipient)
        
        # Always revert to DRAFT on update so it can be re-started if needed
        campaign.status = "DRAFT"
        db.session.commit()
        logger.info(f"Campaign {campaign_id} updated and reset to DRAFT")
        return campaign

    def reset_campaign(self, campaign_id: str, user_id: str = None) -> Campaign | None:
        campaign = self.repository.get_by_id(campaign_id)
        if not campaign:
            return None
        
        # Authorization check
        if user_id and campaign.user_id and campaign.user_id != user_id:
            return None
        
        logger.info(f"Resetting campaign {campaign_id} to DRAFT...")
        campaign.status = "DRAFT"
        reset_count = 0
        for recipient in campaign.recipients:
            logger.info(f"Resetting recipient {recipient.email} (Current status: {recipient.status})")
            recipient.status = "PENDING"
            recipient.email_id = None 
            recipient.email_record = None # Explicitly clear relationship to old record
            reset_count += 1
            
        db.session.commit()
        logger.info(f"Campaign {campaign_id} reset to DRAFT. {reset_count} recipients set to PENDING.")
        return campaign

    def delete_campaign(self, campaign_id: str, user_id: str = None) -> bool:
        campaign = self.repository.get_by_id(campaign_id)
        if not campaign:
            return False
        
        # Authorization check
        if user_id and campaign.user_id and campaign.user_id != user_id:
            return False
        
        logger.info(f"Deleting campaign {campaign_id}...")
        return self.repository.delete(campaign_id)

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

    def create_campaign(self, name: str, subject: str, body: str, recipient_emails: list[str]) -> Campaign:
        campaign = Campaign(
            name=name,
            subject=subject,
            body=body,
            status="DRAFT"
        )
        self.repository.create(campaign)
        
        for email in recipient_emails:
            recipient = CampaignRecipient(
                campaign_id=campaign.id,
                email=email,
                status="PENDING"
            )
            self.repository.add_recipient(recipient)
            
        return campaign

    def start_campaign(self, campaign_id: str):
        campaign = self.repository.get_by_id(campaign_id)
        if not campaign or campaign.status == "SENDING":
            return
        
        campaign.status = "SENDING"
        self.repository.update_campaign_status(campaign.id, "SENDING")
        
        logger.info(f"Starting campaign: {campaign.name} ({campaign.id})")
        
        for recipient in campaign.recipients:
            if recipient.status != "PENDING":
                continue
            
            try:
                # Basic variable substitution: {{email}}
                personalized_subject = campaign.subject.replace("{{email}}", recipient.email)
                personalized_body = campaign.body.replace("{{email}}", recipient.email)
                
                # Send using existing EmailService (this creates an Email record for tracking)
                result = self.email_service.send_single_email(
                    recipient=recipient.email,
                    message=personalized_body,
                    subject=personalized_subject
                )
                
                if result:
                    recipient.status = result.status
                    recipient.email_id = result.id
                
            except Exception as e:
                logger.error(f"Failed to send campaign email to {recipient.email}: {e}")
                recipient.status = "FAILED"
        
        campaign.status = "COMPLETED"
        self.repository.update_campaign_status(campaign.id, "COMPLETED")
        logger.info(f"Campaign completed: {campaign.name}")

    def get_all_campaigns(self) -> list[Campaign]:
        return self.repository.get_all()

    def get_campaign_details(self, campaign_id: str) -> dict | None:
        campaign = self.repository.get_by_id(campaign_id)
        if not campaign:
            return None
        
        return {
            "campaign": campaign.to_dict(),
            "recipients": [r.to_dict() for r in campaign.recipients]
        }

    def update_campaign(self, campaign_id: str, name: str, subject: str, body: str, recipient_emails: list[str]) -> Campaign | None:
        campaign = self.repository.get_by_id(campaign_id)
        if not campaign:
            return None
        
        campaign.name = name
        campaign.subject = subject
        campaign.body = body
        
        # If campaign is in DRAFT or COMPLETED, we can refresh recipients
        # For now, let's just refresh them all for simplicity
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

    def reset_campaign(self, campaign_id: str) -> Campaign | None:
        campaign = self.repository.get_by_id(campaign_id)
        if not campaign:
            return None
        
        logger.info(f"Resetting campaign {campaign_id} to DRAFT...")
        campaign.status = "DRAFT"
        reset_count = 0
        for recipient in campaign.recipients:
            recipient.status = "PENDING"
            recipient.email_id = None # Break link to old tracking record if re-sending
            reset_count += 1
            
        db.session.commit()
        logger.info(f"Campaign {campaign_id} reset to DRAFT. {reset_count} recipients set to PENDING.")
        return campaign

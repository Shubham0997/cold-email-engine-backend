import logging
from app.domain.models import Campaign, CampaignRecipient, db
from sqlalchemy.exc import SQLAlchemyError

class CampaignRepository:
    def create(self, campaign: Campaign) -> Campaign:
        try:
            db.session.add(campaign)
            db.session.commit()
            return campaign
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Error creating campaign: {e}")
            raise
    
    def get_by_id(self, campaign_id: str) -> Campaign:
        return db.session.get(Campaign, campaign_id)

    def get_all(self) -> list[Campaign]:
        return db.session.query(Campaign).order_by(Campaign.created_at.desc()).all()

    def add_recipient(self, recipient: CampaignRecipient) -> CampaignRecipient:
        try:
            db.session.add(recipient)
            db.session.commit()
            return recipient
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Error adding recipient: {e}")
            raise

    def update_campaign_status(self, campaign_id: str, status: str):
        try:
            campaign = self.get_by_id(campaign_id)
            if campaign:
                campaign.status = status
                db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Error updating campaign status: {e}")
            raise

    def delete_recipients_by_campaign_id(self, campaign_id: str):
        try:
            db.session.query(CampaignRecipient).filter_by(campaign_id=campaign_id).delete()
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Error deleting recipients: {e}")
            raise

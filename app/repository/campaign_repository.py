import logging
from app.domain.models import Campaign, CampaignRecipient, db
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

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
        return db.session.query(Campaign).options(joinedload(Campaign.recipients)).filter_by(id=campaign_id).first()

    def get_all(self, user_id: str = None) -> list[Campaign]:
        query = db.session.query(Campaign).options(joinedload(Campaign.recipients))
        if user_id:
            query = query.filter(Campaign.user_id == user_id)
        return query.order_by(Campaign.created_at.desc()).all()

    def get_by_name(self, name: str, user_id: str = None) -> Campaign:
        query = db.session.query(Campaign).options(joinedload(Campaign.recipients)).filter_by(name=name)
        if user_id:
            query = query.filter(Campaign.user_id == user_id)
        return query.first()

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

    def delete(self, campaign_id: str):
        try:
            # SQLAlchemy handle cascade if configured, but let's be explicit
            self.delete_recipients_by_campaign_id(campaign_id)
            campaign = self.get_by_id(campaign_id)
            if campaign:
                db.session.delete(campaign)
                db.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Error deleting campaign: {e}")
            raise

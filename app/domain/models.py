from datetime import datetime
import uuid
from app import db

class Email(db.Model):
    __tablename__ = 'emails'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_email = db.Column(db.String(255), nullable=False, index=True)
    subject = db.Column(db.String(255), default="Quick Message")
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default="PENDING") # PENDING, SENT, OPENED, FAILED
    opened_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "recipient_email": self.recipient_email,
            "subject": self.subject,
            "body": self.body,
            "status": self.status,
            "opened_at": self.opened_at.isoformat() + "Z" if self.opened_at else None,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None
        }

class Campaign(db.Model):
    __tablename__ = 'campaigns'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False, unique=True)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default="DRAFT") # DRAFT, SENDING, COMPLETED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    recipients = db.relationship('CampaignRecipient', backref='campaign', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "subject": self.subject,
            "body": self.body,
            "status": self.status,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "total_recipients": len(self.recipients)
        }

class CampaignRecipient(db.Model):
    __tablename__ = 'campaign_recipients'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = db.Column(db.String(36), db.ForeignKey('campaigns.id'), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    status = db.Column(db.String(50), default="PENDING") # PENDING, SENT, FAILED
    email_id = db.Column(db.String(36), db.ForeignKey('emails.id'), nullable=True, index=True) # Link to individual tracking record
    email_record = db.relationship('Email', foreign_keys=[email_id], lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "email": self.email,
            "status": self.status,
            "email_id": self.email_id,
            "opened_at": self.email_record.opened_at.isoformat() + "Z" if self.email_record and self.email_record.opened_at else None
        }

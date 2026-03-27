from datetime import datetime
import uuid
from app import db

class Email(db.Model):
    __tablename__ = 'emails'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), default="Quick Message")
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default="PENDING") # PENDING, SENT, OPENED, FAILED
    opened_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "recipient_email": self.recipient_email,
            "subject": self.subject,
            "body": self.body,
            "status": self.status,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

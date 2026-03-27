from app.domain.models import Email, db
from sqlalchemy.exc import SQLAlchemyError
import logging

class EmailRepository:
    def create(self, email: Email) -> Email:
        try:
            db.session.add(email)
            db.session.commit()
            return email
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Error creating email: {e}")
            raise
    
    def get_by_id(self, email_id: str) -> Email:
        return db.session.get(Email, email_id)

    def get_all(self) -> list[Email]:
        return db.session.query(Email).order_by(Email.created_at.desc()).all()

    def update(self, email: Email) -> Email:
        try:
            db.session.commit()
            return email
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Error updating email: {e}")
            raise

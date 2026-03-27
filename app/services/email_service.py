import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging
import socket
from app.domain.models import Email, CampaignRecipient, Campaign
from app.repository.email_repository import EmailRepository
from app import db
from datetime import datetime
from sqlalchemy import func

logger = logging.getLogger(__name__)

class SmtpConnectionContext:
    def __init__(self, service: 'EmailService'):
        self.service = service
        self.server: any = None

    def __enter__(self):
        self.server = self.service._create_smtp_connection()
        return self.server

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.server:
            try:
                self.server.quit()
            except:
                pass

class EmailService:
    def __init__(self, repository: EmailRepository):
        self.repository = repository
        # Sanitize all env variables to avoid hidden characters/spaces
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com').strip()
        self.smtp_port = int(str(os.getenv('SMTP_PORT', '587')).strip())
        self.smtp_user = os.getenv('SMTP_USER', '').strip() or None
        self.smtp_pass = os.getenv('SMTP_PASS', '').strip() or None
    
    def smtp_connection(self):
        """Returns a context manager for SMTP connection reuse."""
        return SmtpConnectionContext(self)
    
    def construct_html(self, body: str, email_id: str) -> str:
        tracking_base = os.getenv('TRACKING_BASE_URL', 'http://localhost:5000')
        tracking_url = f"{tracking_base}/track/open/{email_id}"
        # Ensure newlines are parsed as <br>
        body_html = body.replace('\n', '<br>')
        html = f"""
        <html>
            <body>
                <p>{body_html}</p>
                <img src="{tracking_url}" width="1" height="1" border="0" alt="" />
            </body>
        </html>
        """
        return html

    def register_email(self, recipient: str, message: str, subject: str = "Quick Message") -> Email:
        """Creates an email record in the DB and returns it (with ID) immediately."""
        email_record = Email(recipient_email=recipient, body=message, subject=subject, status="PENDING")
        self.repository.create(email_record)
        return email_record

    def _create_smtp_connection(self):
        """Creates and authenticates a fresh SMTP connection."""
        if not (self.smtp_user and self.smtp_pass):
            return None
            
        local_hostname = "cold-email-engine.local"
        logger.info(f"Establishing SMTP connection to {self.smtp_host}:{self.smtp_port}")
        
        try:
            try:
                ip = socket.gethostbyname(self.smtp_host)
            except Exception:
                ip = "142.251.2.108" # Gmail fallback
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((ip, self.smtp_port))
            
            if self.smtp_port == 465:
                import ssl
                context = ssl.create_default_context()
                sock = context.wrap_socket(sock, server_hostname=self.smtp_host)
                server = smtplib.SMTP_SSL(local_hostname=local_hostname)
            else:
                server = smtplib.SMTP(local_hostname=local_hostname)
            
            server._host = self.smtp_host # type: ignore
            server.sock = sock
            server.file = sock.makefile('rb')
            
            server.getreply()
            server.ehlo_or_helo_if_needed()
            
            if self.smtp_port != 465:
                server.starttls()
                server.ehlo_or_helo_if_needed()
            
            server.login(self.smtp_user, self.smtp_pass)
            logger.info("SMTP connection established and authenticated.")
            return server
            
        except Exception as e:
            logger.error(f"Failed to establish SMTP connection: {e}")
            raise e

    def send_email_by_record(self, email_record: Email, server=None) -> Email:
        """Sends an email record. Optionally reuses an existing authenticated SMTP server."""
        recipient = email_record.recipient_email
        message = email_record.body
        subject = email_record.subject
        
        html_content = self.construct_html(message, email_record.id)

        msg = MIMEMultipart("alternative")
        msg['Subject'] = subject
        msg['From'] = self.smtp_user or "noreply@coldemailengine.local"
        msg['To'] = recipient

        part = MIMEText(html_content, 'html')
        msg.attach(part)

        try:
            if self.smtp_user and self.smtp_pass:
                if server:
                    # Reuse connection
                    server.send_message(msg)
                    email_record.created_at = datetime.utcnow()
                else:
                    # One-off connection
                    with self.smtp_connection() as conn:
                        if conn:
                            conn.send_message(msg)
                            email_record.created_at = datetime.utcnow()
                        else:
                            logger.warning("SMTP credentials present but connection failed. Simulating send.")
            else:
                logger.warning("SMTP credentials missing. Simulating successful send.")
            
            if email_record.status == "PENDING":
                email_record.status = "SENT"
        except Exception as e:
            logger.error(f"Failed to send email {email_record.id}: {type(e).__name__}: {e}", exc_info=True)
            email_record.status = "FAILED"
        
        self.repository.update(email_record)
        return email_record

    def send_single_email(self, recipient: str, message: str, subject: str = "Quick Message") -> Email:
        # Backward compatibility / simple wrapper
        email_record = self.register_email(recipient, message, subject)
        return self.send_email_by_record(email_record)

    def track_open(self, email_id: str) -> bool:
        email = self.repository.get_by_id(email_id)
        if email:
            if email.status != "OPENED":
                # FILTER: If hit happens within 30 seconds of creation, it's likely an automated delivery scan
                time_since_creation = (datetime.utcnow() - email.created_at).total_seconds()
                if time_since_creation < 30:
                    logger.warning(f"Ignoring instant tracking hit (delivery scan): {email_id} ({time_since_creation:.1f}s)")
                    return False

                email.status = "OPENED"
                email.opened_at = datetime.utcnow()
                self.repository.update(email)
                
                # ALSO Update CampaignRecipient if this email belongs to a campaign
                try:
                    recipient = db.session.query(CampaignRecipient).filter_by(email_id=email_id).first()
                    if recipient:
                        logger.info(f"Syncing status for CampaignRecipient: {recipient.email} (Campaign: {recipient.campaign_id})")
                        recipient.status = "OPENED"
                        db.session.commit()
                        logger.info(f"Synchronized status for campaign recipient: {recipient.email}")
                    else:
                        logger.info(f"No CampaignRecipient found linked to email_id: {email_id}")
                except Exception as sync_err:
                    logger.error(f"Failed to synchronize status with CampaignRecipient: {sync_err}")

                logger.info(f"Email {email_id} ({email.recipient_email}) marked as OPENED after {time_since_creation:.1f}s")
                return True
            else:
                logger.info(f"Email {email_id} was already opened. Ignoring idempotently.")
                return False
        
        logger.warning(f"Tracking pixel requested for non-existent email_id: {email_id}")
        return False

    def get_dashboard_stats(self) -> dict:
        # 1. High-level counts via SQL aggregations
        total_emails = db.session.query(func.count(Email.id)).scalar() or 0
        opened_emails = db.session.query(func.count(Email.id)).filter(Email.status == "OPENED").scalar() or 0
        open_rate = (opened_emails / total_emails * 100) if total_emails > 0 else 0
        
        logger.info(f"Dashboard Stats: Optimized aggregation (Total: {total_emails}, Opened: {opened_emails})")

        # 2. Fetch enriched emails using a more efficient join
        # We join Email with CampaignRecipient and Campaign to get everything in one query
        results = (
            db.session.query(Email, Campaign.id, Campaign.name)
            .outerjoin(CampaignRecipient, CampaignRecipient.email_id == Email.id)
            .outerjoin(Campaign, Campaign.id == CampaignRecipient.campaign_id)
            .order_by(Email.created_at.desc())
            .all()
        )

        enriched_emails = []
        for email_obj, campaign_id, campaign_name in results:
            email_dict = email_obj.to_dict()
            email_dict['campaign_id'] = campaign_id
            email_dict['campaign_name'] = campaign_name or "Single Send"
            enriched_emails.append(email_dict)

        return {
            "total_emails": total_emails,
            "opened_emails": opened_emails,
            "open_rate": float(f"{open_rate:.1f}"),
            "emails": enriched_emails
        }

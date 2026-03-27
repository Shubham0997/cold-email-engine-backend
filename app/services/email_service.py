import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging
import socket
from app.domain.models import Email
from app.repository.email_repository import EmailRepository
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, repository: EmailRepository):
        self.repository = repository
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_pass = os.getenv('SMTP_PASS')
    
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

    def send_single_email(self, recipient: str, message: str) -> Email:
        email_record = Email(recipient_email=recipient, body=message, status="PENDING")
        self.repository.create(email_record)

        html_content = self.construct_html(message, email_record.id)

        msg = MIMEMultipart("alternative")
        msg['Subject'] = email_record.subject
        msg['From'] = self.smtp_user or "noreply@coldemailengine.local"
        msg['To'] = recipient

        part = MIMEText(html_content, 'html')
        msg.attach(part)

        try:
            if self.smtp_user and self.smtp_pass:
                local_hostname = "cold-email-engine.local"
                logger.info(f"Attempting to send email via {self.smtp_host}:{self.smtp_port} (User: {self.smtp_user})")
                
                # Manual resolution to IPv4 can bypass [Errno 16] DNS issues on Vercel
                try:
                    addr_info = socket.getaddrinfo(self.smtp_host, self.smtp_port, family=socket.AF_INET, type=socket.SOCK_STREAM)
                    resolved_ip = addr_info[0][4][0]
                    logger.info(f"Resolved {self.smtp_host} to {resolved_ip}")
                    target_host = resolved_ip
                except Exception as dns_err:
                    logger.warning(f"Manual DNS resolution failed: {dns_err}. Falling back to hostname.")
                    target_host = self.smtp_host

                if self.smtp_port == 465:
                    logger.info("Using SMTP_SSL (Port 465)")
                    with smtplib.SMTP_SSL(target_host, self.smtp_port, timeout=10, local_hostname=local_hostname) as server:
                        logger.info("SMTP_SSL connection established, attempting login...")
                        server.login(self.smtp_user, self.smtp_pass)
                        logger.info("SMTP login successful, sending message...")
                        server.send_message(msg)
                else:
                    logger.info(f"Using SMTP with STARTTLS (Port {self.smtp_port})")
                    with smtplib.SMTP(target_host, self.smtp_port, timeout=10, local_hostname=local_hostname) as server:
                        logger.info("SMTP connection established, starting TLS...")
                        server.starttls()
                        logger.info("STARTTLS successful, attempting login...")
                        server.login(self.smtp_user, self.smtp_pass)
                        logger.info("SMTP login successful, sending message...")
                        server.send_message(msg)
                
                logger.info(f"Email {email_record.id} sent successfully to {recipient}")
            else:
                logger.warning("SMTP credentials missing. Simulating successful send.")
            
            email_record.status = "SENT"
        except Exception as e:
            logger.error(f"Failed to send email {email_record.id}: {type(e).__name__}: {e}", exc_info=True)
            email_record.status = "FAILED"
        
        self.repository.update(email_record)
        return email_record

    def track_open(self, email_id: str) -> bool:
        email = self.repository.get_by_id(email_id)
        if email:
            if email.status != "OPENED":
                email.status = "OPENED"
                email.opened_at = datetime.utcnow()
                self.repository.update(email)
                logger.info(f"Email opened: {email_id}")
                return True
            else:
                logger.info(f"Email {email_id} was already opened. Ignoring idempotently.")
                return False
        
        logger.warning(f"Tracking pixel requested for non-existent email_id: {email_id}")
        return False

    def get_dashboard_stats(self) -> dict:
        emails = self.repository.get_all()
        total_emails = len(emails)
        opened_emails = sum(1 for e in emails if e.status == "OPENED")
        open_rate = (opened_emails / total_emails * 100) if total_emails > 0 else 0
        
        return {
            "total_emails": total_emails,
            "opened_emails": opened_emails,
            "open_rate": round(open_rate, 1),
            "emails": [e.to_dict() for e in emails]
        }

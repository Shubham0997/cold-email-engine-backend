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
        # Sanitize all env variables to avoid hidden characters/spaces
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com').strip()
        self.smtp_port = int(str(os.getenv('SMTP_PORT', '587')).strip())
        self.smtp_user = os.getenv('SMTP_USER', '').strip() or None
        self.smtp_pass = os.getenv('SMTP_PASS', '').strip() or None
    
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

    def send_single_email(self, recipient: str, message: str, subject: str = "Quick Message") -> Email:
        email_record = Email(recipient_email=recipient, body=message, subject=subject, status="PENDING")
        self.repository.create(email_record)
        
        # ... later in the code ...
        html_content = self.construct_html(message, email_record.id)

        msg = MIMEMultipart("alternative")
        msg['Subject'] = subject
        msg['From'] = self.smtp_user or "noreply@coldemailengine.local"
        msg['To'] = recipient

        part = MIMEText(html_content, 'html')
        msg.attach(part)

        try:
            if self.smtp_user and self.smtp_pass:
                local_hostname = "cold-email-engine.local"
                logger.info(f"Attempting manual socket connection to {self.smtp_host}:{self.smtp_port}")
                
                # Manual socket creation to bypass getaddrinfo EBUSY issue on Vercel
                try:
                    # Resolve IP with fallback to known Gmail SMTP IPs if DNS is broken on Vercel
                    try:
                        ip = socket.gethostbyname(self.smtp_host)
                        logger.info(f"Resolved {self.smtp_host} to {ip}")
                    except Exception as dns_err:
                        logger.warning(f"DNS resolution failed for {self.smtp_host}: {dns_err}. Using fallback IP.")
                        ip = "142.251.2.108" 
                    
                    # Create raw socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(10)
                    sock.connect((ip, self.smtp_port))
                    logger.info(f"Manual socket connection established with {ip}")
                    
                    if self.smtp_port == 465:
                        # For Port 465 (SSL), we must wrap the socket in SSL FIRST
                        import ssl
                        context = ssl.create_default_context()
                        sock = context.wrap_socket(sock, server_hostname=self.smtp_host)
                        server = smtplib.SMTP_SSL(local_hostname=local_hostname)
                    else:
                        # For Port 587
                        server = smtplib.SMTP(local_hostname=local_hostname)
                    
                    # Set _host manually for SSL verification compatibility (works in 3.11 and 3.12)
                    server._host = self.smtp_host # type: ignore
                    server.sock = sock
                    server.file = sock.makefile('rb')
                    
                    # 1. Read the initial server banner (Crucial step!)
                    code, msg_banner = server.getreply()
                    logger.info(f"SMTP Banner: {code} {msg_banner}")
                    
                    # 2. Identify ourselves
                    server.ehlo_or_helo_if_needed()
                    
                    if self.smtp_port != 465:
                        # 3. Start TLS for port 587
                        server.starttls()
                        server.ehlo_or_helo_if_needed()
                    
                    with server:
                        server.login(self.smtp_user, self.smtp_pass)
                        logger.info("SMTP login successful, sending message...")
                        server.send_message(msg)
                        # Reset created_at to the ACTUAL sent time for accurate tracking cooldown
                        email_record.created_at = datetime.utcnow()
                
                except Exception as sock_err:
                    logger.error(f"Manual socket SMTP failed: {sock_err}")
                    raise sock_err
                
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
                # FILTER: If hit happens within 15 seconds of creation, it's likely an automated delivery check
                time_since_creation = (datetime.utcnow() - email.created_at).total_seconds()
                if time_since_creation < 15:
                    logger.warning(f"Ignoring instant tracking hit (automated scan): {email_id} ({time_since_creation:.1f}s)")
                    return False

                email.status = "OPENED"
                email.opened_at = datetime.utcnow()
                self.repository.update(email)
                logger.info(f"Email opened: {email_id} after {time_since_creation:.1f}s")
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
            "open_rate": float(f"{open_rate:.1f}"),
            "emails": [e.to_dict() for e in emails]
        }

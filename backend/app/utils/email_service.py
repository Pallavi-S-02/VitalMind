import os
import smtplib
from email.message import EmailMessage
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class SmtpResult:
    success: bool
    error: Optional[str] = None
    degraded: bool = False

def send_smtp_email(to_email: str, subject: str, html_body: str = None, text_body: str = None) -> SmtpResult:
    """Send an email using generic SMTP configuration defined in .env."""
    
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    sender_email = os.getenv("SENDER_EMAIL", smtp_user)
    
    if not all([smtp_server, smtp_port, smtp_user, smtp_pass, sender_email]):
        error_msg = "SMTP credentials missing in environment variables (.env). Cannot send email."
        logger.error(error_msg)
        return SmtpResult(success=False, error=error_msg)
        
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email
        
        if text_body:
            msg.set_content(text_body)
        
        if html_body:
            if text_body:
                msg.add_alternative(html_body, subtype='html')
            else:
                # If only HTML is provided, we set it as the primary content
                msg.set_content(html_body, subtype='html')

        port = int(smtp_port)
        
        # Determine whether to use SSL or STARTTLS based on port
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_server, port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_server, port, timeout=15)
            server.starttls()
            
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Successfully sent SMTP email to {to_email} with subject: {subject}")
        return SmtpResult(success=True)
        
    except Exception as e:
        logger.exception(f"SMTP email failed to send to {to_email}: {e}")
        return SmtpResult(success=False, error=str(e))

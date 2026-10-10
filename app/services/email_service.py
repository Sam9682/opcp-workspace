"""Email service for sending notifications and invoices
Feature: OPCP-website
Validates Requirements 4.4, 10.1, 10.2, 10.3, 10.5
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails
    
    Validates Requirements 4.4:
    - Sends invoice PDFs to member's email address
    """
    
    def __init__(self):
        """Initialize email service with SMTP configuration"""
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_from = settings.SMTP_FROM
        logger.info(f"Email service initialized with SMTP host: {self.smtp_host}")
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        attachments: Optional[List[str]] = None
    ) -> bool:
        """Send an email with optional attachments
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body_text: Plain text email body
            body_html: HTML email body (optional)
            attachments: List of file paths to attach (optional)
        
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_from
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add text body
            text_part = MIMEText(body_text, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Add HTML body if provided
            if body_html:
                html_part = MIMEText(body_html, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Add attachments if provided
            if attachments:
                for filepath in attachments:
                    if Path(filepath).exists():
                        with open(filepath, 'rb') as f:
                            attachment = MIMEApplication(f.read(), _subtype='pdf')
                            attachment.add_header(
                                'Content-Disposition',
                                'attachment',
                                filename=Path(filepath).name
                            )
                            msg.attach(attachment)
                        logger.info(f"Attached file: {filepath}")
                    else:
                        logger.warning(f"Attachment not found: {filepath}")
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}", exc_info=True)
            return False
    
    def send_invoice_email(
        self,
        to_email: str,
        user_name: str,
        invoice_number: str,
        amount: float,
        currency: str,
        invoice_path: str
    ) -> bool:
        """Send invoice email with PDF attachment
        
        Validates Requirements 4.4:
        - Sends invoice PDF to member's email address
        
        Args:
            to_email: Recipient email address
            user_name: User's full name
            invoice_number: Invoice number
            amount: Payment amount
            currency: Currency code
            invoice_path: Path to invoice PDF file
        
        Returns:
            True if email sent successfully, False otherwise
        """
        subject = f"Votre facture OPCP - {invoice_number}"
        
        body_text = f"""
Bonjour {user_name},

Merci pour votre paiement de cotisation annuelle OPCP.

Détails de votre paiement :
- Numéro de facture : {invoice_number}
- Montant : {amount:.2f} {currency}

Vous trouverez votre facture en pièce jointe.

Cordialement,
L'équipe OPCP

---

Hello {user_name},

Thank you for your OPCP annual membership payment.

Payment details:
- Invoice number: {invoice_number}
- Amount: {amount:.2f} {currency}

You will find your invoice attached.

Best regards,
The OPCP Team
"""
        
        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #1a1a1a; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f9f9f9; }}
        .details {{ background-color: white; padding: 15px; margin: 20px 0; border-left: 4px solid #1a1a1a; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OPCP</h1>
        </div>
        <div class="content">
            <p>Bonjour {user_name},</p>
            <p>Merci pour votre paiement de cotisation annuelle OPCP.</p>
            
            <div class="details">
                <h3>Détails de votre paiement / Payment Details</h3>
                <p><strong>Numéro de facture / Invoice number:</strong> {invoice_number}</p>
                <p><strong>Montant / Amount:</strong> {amount:.2f} {currency}</p>
            </div>
            
            <p>Vous trouverez votre facture en pièce jointe.</p>
            <p>You will find your invoice attached.</p>
            
            <p>Cordialement / Best regards,<br>
            L'équipe OPCP / The OPCP Team</p>
        </div>
        <div class="footer">
            <p>PSMC OPCP - OVH</p>
        </div>
    </div>
</body>
</html>
"""
        
        return self.send_email(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=[invoice_path]
        )


# Global email service instance
email_service = EmailService()

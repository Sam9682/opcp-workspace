"""Email service for sending notifications and verification emails.

This module provides email sending functionality using SMTP,
as required by Requirements 2.6, 4.4, 6.4, 6.6, 10.1-10.5.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.config import settings
from app.logging_config import logger


class EmailService:
    """Service for sending emails via SMTP"""
    
    def __init__(self):
        """Initialize email service with SMTP configuration"""
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_from = settings.SMTP_FROM
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> bool:
        """Send an email via SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_body: HTML version of email body
            text_body: Plain text version of email body (optional)
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        # Check if SMTP is properly configured
        if not self.smtp_password or self.smtp_password == "your-email-password":
            logger.warning(f"SMTP not configured - skipping email to {to_email}. Please set SMTP_PASSWORD in .env")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_from
            msg['To'] = to_email
            
            # Add text and HTML parts
            if text_body:
                part1 = MIMEText(text_body, 'plain')
                msg.attach(part1)
            
            part2 = MIMEText(html_body, 'html')
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed for {to_email}: {str(e)}. Check SMTP_USER and SMTP_PASSWORD in .env")
            return False
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_verification_email(
        self,
        to_email: str,
        verification_token: str,
        user_name: str
    ) -> bool:
        """Send email verification link to new user.
        
        Args:
            to_email: User's email address
            verification_token: Token for email verification
            user_name: User's first name for personalization
            
        Returns:
            True if email was sent successfully, False otherwise
            
        Validates: Requirements 2.6
        """
        subject = "Verify your OPCP account"
        
        verification_url = f"https://opcp-psmc.com/api/auth/verify-email?token={verification_token}"
        
        html_body = f"""
        <html>
            <body>
                <h2>Welcome to OPCP, {user_name}!</h2>
                <p>Thank you for registering. Please verify your email address by clicking the link below:</p>
                <p><a href="{verification_url}">Verify Email Address</a></p>
                <p>If you didn't create an account, you can safely ignore this email.</p>
                <p>Best regards,<br>The OPCP Team</p>
            </body>
        </html>
        """
        
        text_body = f"""
        Welcome to OPCP, {user_name}!
        
        Thank you for registering. Please verify your email address by visiting:
        {verification_url}
        
        If you didn't create an account, you can safely ignore this email.
        
        Best regards,
        The OPCP Team
        """
        
        return self.send_email(to_email, subject, html_body, text_body)
    
    def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_name: str
    ) -> bool:
        """Send password reset link to user."""
        subject = "Réinitialisation de votre mot de passe OPCP"
        
        reset_url = f"https://opcp-psmc.com/reset-password?token={reset_token}"
        
        html_body = f"""
        <html>
            <body>
                <h2>Bonjour {user_name},</h2>
                <p>Vous avez demandé à réinitialiser votre mot de passe OPCP.</p>
                <p>Cliquez sur le lien ci-dessous pour créer un nouveau mot de passe :</p>
                <p><a href="{reset_url}">Réinitialiser mon mot de passe</a></p>
                <p>Ce lien est valide pendant 1 heure.</p>
                <p>Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.</p>
                <p>Cordialement,<br>L'équipe OPCP</p>
            </body>
        </html>
        """
        
        text_body = f"""
        Bonjour {user_name},
        
        Vous avez demandé à réinitialiser votre mot de passe OPCP.
        
        Visitez ce lien pour créer un nouveau mot de passe :
        {reset_url}
        
        Ce lien est valide pendant 1 heure.
        
        Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.
        
        Cordialement,
        L'équipe OPCP
        """
        
        return self.send_email(to_email, subject, html_body, text_body)
    
    def send_2fa_code_email(
        self,
        to_email: str,
        code: str,
        user_name: str
    ) -> bool:
        """Send a two-factor authentication verification code to the user.
        
        Args:
            to_email: User's email address
            code: The verification code to send
            user_name: User's first name for personalization
            
        Returns:
            True if email was sent successfully, False otherwise
            
        Validates: Requirements 7.2
        """
        subject = "Votre code de vérification OPCP"
        
        html_body = f"""
        <html>
            <body>
                <h2>Bonjour {user_name},</h2>
                <p>Voici votre code de vérification pour vous connecter à votre compte OPCP :</p>
                <p style="font-size: 24px; font-weight: bold; letter-spacing: 4px;">{code}</p>
                <p>Ce code est valide pendant 5 minutes.</p>
                <p>Si vous n'avez pas tenté de vous connecter, ignorez cet email.</p>
                <p>Cordialement,<br>L'équipe OPCP</p>
            </body>
        </html>
        """
        
        text_body = f"""
        Bonjour {user_name},
        
        Voici votre code de vérification pour vous connecter à votre compte OPCP :
        
        {code}
        
        Ce code est valide pendant 5 minutes.
        
        Si vous n'avez pas tenté de vous connecter, ignorez cet email.
        
        Cordialement,
        L'équipe OPCP
        """
        
        return self.send_email(to_email, subject, html_body, text_body)


# Global email service instance
email_service = EmailService()

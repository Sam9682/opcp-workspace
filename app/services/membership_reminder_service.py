"""Membership expiry reminder service
Feature: OPCP-website
Validates Requirements 4.6
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class MembershipReminderService:
    """Service for sending membership expiry reminders
    
    Validates Requirements 4.6:
    - Sends renewal reminder email 30 days before membership expiration
    """
    
    def __init__(self):
        """Initialize membership reminder service"""
        self.reminder_days_before = 30
        logger.info("Membership reminder service initialized")
    
    def get_expiring_memberships(self, db: Session) -> List[User]:
        """Get users whose membership expires in 30 days
        
        Args:
            db: Database session
        
        Returns:
            List of users with memberships expiring in 30 days
        """
        # Calculate the target date (30 days from now)
        # Use date truncation to avoid time precision issues
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        target_date_start = now + timedelta(days=self.reminder_days_before)
        target_date_end = target_date_start + timedelta(days=1)
        
        # Query users whose membership expires in 30 days
        # Note: We use replace(tzinfo=None) for SQLite compatibility
        stmt = select(User).where(
            User.membership_expires_at >= target_date_start.replace(tzinfo=None),
            User.membership_expires_at < target_date_end.replace(tzinfo=None),
            User.is_email_verified == True
        )
        
        result = db.execute(stmt)
        users = result.scalars().all()
        
        logger.info(f"Found {len(users)} users with memberships expiring in {self.reminder_days_before} days")
        return list(users)
    
    def send_expiry_reminder(self, user: User) -> bool:
        """Send membership expiry reminder email to a user
        
        Args:
            user: User to send reminder to
        
        Returns:
            True if email sent successfully, False otherwise
        """
        if not user.membership_expires_at:
            logger.warning(f"User {user.email} has no membership expiration date")
            return False
        
        expiry_date = user.membership_expires_at.strftime("%d/%m/%Y")
        user_name = f"{user.first_name} {user.last_name}"
        
        subject = "Rappel de renouvellement - OPCP Membership Renewal Reminder"
        
        body_text = f"""
Bonjour {user_name},

Votre adhésion à l'PSMC OPCP expire le {expiry_date}.

Pour continuer à profiter de tous les avantages de votre adhésion, nous vous invitons à renouveler votre cotisation dès maintenant.

Vous pouvez renouveler votre adhésion en vous connectant à votre espace membre et en effectuant un paiement en ligne.

Merci de votre confiance et de votre soutien à OPCP.

Cordialement,
L'équipe OPCP

---

Hello {user_name},

Your OPCP membership expires on {expiry_date}.

To continue enjoying all the benefits of your membership, we invite you to renew your subscription now.

You can renew your membership by logging into your member area and making an online payment.

Thank you for your trust and support of OPCP.

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
        .alert {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
        .cta {{ text-align: center; margin: 30px 0; }}
        .button {{ display: inline-block; padding: 12px 30px; background-color: #1a1a1a; color: white; text-decoration: none; border-radius: 5px; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OPCP</h1>
            <p>Rappel de renouvellement / Renewal Reminder</p>
        </div>
        <div class="content">
            <p>Bonjour {user_name},</p>
            
            <div class="alert">
                <strong>⚠️ Votre adhésion expire bientôt / Your membership expires soon</strong>
                <p>Date d'expiration / Expiry date: <strong>{expiry_date}</strong></p>
            </div>
            
            <p>Pour continuer à profiter de tous les avantages de votre adhésion, nous vous invitons à renouveler votre cotisation dès maintenant.</p>
            
            <p>To continue enjoying all the benefits of your membership, we invite you to renew your subscription now.</p>
            
            <div class="cta">
                <p><strong>Connectez-vous pour renouveler / Log in to renew</strong></p>
            </div>
            
            <p>Merci de votre confiance et de votre soutien à OPCP.</p>
            <p>Thank you for your trust and support of OPCP.</p>
            
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
        
        success = email_service.send_email(
            to_email=user.email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )
        
        if success:
            logger.info(f"Sent expiry reminder to {user.email}")
        else:
            logger.error(f"Failed to send expiry reminder to {user.email}")
        
        return success
    
    def process_expiry_reminders(self, db: Session) -> dict:
        """Process all expiring memberships and send reminders
        
        Args:
            db: Database session
        
        Returns:
            Dictionary with processing results (total, sent, failed)
        """
        users = self.get_expiring_memberships(db)
        
        sent_count = 0
        failed_count = 0
        
        for user in users:
            if self.send_expiry_reminder(user):
                sent_count += 1
            else:
                failed_count += 1
        
        result = {
            "total": len(users),
            "sent": sent_count,
            "failed": failed_count
        }
        
        logger.info(f"Processed expiry reminders: {result}")
        return result


# Global membership reminder service instance
membership_reminder_service = MembershipReminderService()

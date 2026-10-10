"""Event reminder service
Feature: OPCP-website
Validates Requirements 6.4
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, EventRegistration, User, EventStatus
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class EventReminderService:
    """Service for sending event reminders
    
    Validates Requirements 6.4:
    - Sends reminder emails 7 days before event
    - Only sends to registered participants
    """
    
    def __init__(self):
        """Initialize event reminder service"""
        self.reminder_days_before = 7
        logger.info("Event reminder service initialized")
    
    def get_upcoming_events(self, db: Session) -> List[Event]:
        """Get events that start in 7 days
        
        Args:
            db: Database session
        
        Returns:
            List of events starting in 7 days
        """
        # Calculate the target date (7 days from now)
        # Use date truncation to avoid time precision issues
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        target_date_start = now + timedelta(days=self.reminder_days_before)
        target_date_end = target_date_start + timedelta(days=1)
        
        # Query events that start in 7 days and are scheduled (not cancelled)
        # Note: We use replace(tzinfo=None) for SQLite compatibility
        stmt = select(Event).where(
            Event.start_date >= target_date_start.replace(tzinfo=None),
            Event.start_date < target_date_end.replace(tzinfo=None),
            Event.status == EventStatus.SCHEDULED
        )
        
        result = db.execute(stmt)
        events = result.scalars().all()
        
        logger.info(f"Found {len(events)} events starting in {self.reminder_days_before} days")
        return list(events)
    
    def get_event_participants(self, db: Session, event_id: str) -> List[User]:
        """Get all registered participants for an event
        
        Args:
            db: Database session
            event_id: Event UUID
        
        Returns:
            List of users registered for the event
        """
        # Query users who are registered for this event
        stmt = select(User).join(
            EventRegistration,
            User.id == EventRegistration.user_id
        ).where(
            EventRegistration.event_id == event_id,
            User.is_email_verified == True
        )
        
        result = db.execute(stmt)
        users = result.scalars().all()
        
        logger.info(f"Found {len(users)} registered participants for event {event_id}")
        return list(users)
    
    def send_event_reminder(self, user: User, event: Event) -> bool:
        """Send event reminder email to a participant
        
        Args:
            user: User to send reminder to
            event: Event to remind about
        
        Returns:
            True if email sent successfully, False otherwise
        """
        # Format dates for email
        start_date_str = event.start_date.strftime("%d/%m/%Y à %H:%M")
        end_date_str = event.end_date.strftime("%d/%m/%Y à %H:%M")
        user_name = f"{user.first_name} {user.last_name}"
        
        subject = f"Rappel : {event.title} - OPCP Event Reminder"
        
        body_text = f"""
Bonjour {user_name},

Ceci est un rappel pour l'événement OPCP auquel vous êtes inscrit(e) :

Titre : {event.title}
Date de début : {start_date_str}
Date de fin : {end_date_str}
Lieu : {event.location or 'Non spécifié'}

{event.description or ''}

L'événement aura lieu dans {self.reminder_days_before} jours. Nous avons hâte de vous y voir !

Si vous ne pouvez plus participer, pensez à vous désinscrire depuis votre espace membre.

Cordialement,
L'équipe OPCP

---

Hello {user_name},

This is a reminder for the OPCP event you are registered for:

Title: {event.title}
Start date: {start_date_str}
End date: {end_date_str}
Location: {event.location or 'Not specified'}

{event.description or ''}

The event will take place in {self.reminder_days_before} days. We look forward to seeing you there!

If you can no longer attend, please unregister from your member area.

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
        .event-details {{ background-color: white; padding: 15px; margin: 20px 0; border-left: 4px solid #1a1a1a; }}
        .reminder-badge {{ background-color: #4CAF50; color: white; padding: 10px 20px; border-radius: 5px; display: inline-block; margin: 10px 0; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OPCP</h1>
            <h2>Rappel d'événement / Event Reminder</h2>
        </div>
        <div class="content">
            <p>Bonjour {user_name},</p>
            
            <div class="reminder-badge">
                📅 Dans {self.reminder_days_before} jours / In {self.reminder_days_before} days
            </div>
            
            <p>Ceci est un rappel pour l'événement OPCP auquel vous êtes inscrit(e) :</p>
            <p>This is a reminder for the OPCP event you are registered for:</p>
            
            <div class="event-details">
                <h3>{event.title}</h3>
                <p><strong>Date de début / Start date:</strong> {start_date_str}</p>
                <p><strong>Date de fin / End date:</strong> {end_date_str}</p>
                <p><strong>Lieu / Location:</strong> {event.location or 'Non spécifié / Not specified'}</p>
                {f'<p><strong>Description:</strong></p><p>{event.description}</p>' if event.description else ''}
            </div>
            
            <p>Nous avons hâte de vous y voir !</p>
            <p>We look forward to seeing you there!</p>
            
            <p><em>Si vous ne pouvez plus participer, pensez à vous désinscrire depuis votre espace membre.</em></p>
            <p><em>If you can no longer attend, please unregister from your member area.</em></p>
            
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
            logger.info(f"Sent event reminder to {user.email} for event {event.id} ({event.title})")
        else:
            logger.error(f"Failed to send event reminder to {user.email} for event {event.id}")
        
        return success
    
    def process_event_reminders(self, db: Session) -> dict:
        """Process all upcoming events and send reminders to registered participants
        
        Args:
            db: Database session
        
        Returns:
            Dictionary with processing results (events, participants, sent, failed)
        """
        events = self.get_upcoming_events(db)
        
        total_participants = 0
        sent_count = 0
        failed_count = 0
        
        for event in events:
            participants = self.get_event_participants(db, event.id)
            total_participants += len(participants)
            
            for participant in participants:
                if self.send_event_reminder(participant, event):
                    sent_count += 1
                else:
                    failed_count += 1
        
        result = {
            "events": len(events),
            "participants": total_participants,
            "sent": sent_count,
            "failed": failed_count
        }
        
        logger.info(f"Processed event reminders: {result}")
        return result


# Global event reminder service instance
event_reminder_service = EventReminderService()

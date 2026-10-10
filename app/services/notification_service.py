"""Notification service for delivering notifications to users
Feature: OPCP-website
Validates Requirements 10.1, 10.2, 10.3, 10.5

This service handles the delivery of notifications to users based on their preferences.
It checks user notification preferences before sending notifications and supports
asynchronous delivery through a message queue (optional).
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import (
    User, 
    Notification, 
    NotificationPreferences, 
    NotificationType,
    UserRole
)
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for delivering notifications to users
    
    Validates Requirements 10.1, 10.2, 10.3, 10.5:
    - Sends forum reply notifications
    - Sends event notifications
    - Sends announcements
    - Checks user preferences before sending
    """
    
    def __init__(self):
        """Initialize notification service"""
        self.email_service = email_service
        logger.info("NotificationService initialized")
    
    def _get_user_preferences(
        self, 
        db: Session, 
        user_id
    ) -> NotificationPreferences:
        """Get user notification preferences, creating defaults if none exist
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            NotificationPreferences object
        """
        preferences = db.query(NotificationPreferences).filter(
            NotificationPreferences.user_id == user_id
        ).first()
        
        if not preferences:
            # Create default preferences
            preferences = NotificationPreferences(
                user_id=user_id,
                email_notifications=True,
                forum_notifications=True,
                event_notifications=True,
                announcement_notifications=True
            )
            db.add(preferences)
            db.commit()
            db.refresh(preferences)
            logger.info(f"Created default notification preferences for user {user_id}")
        
        return preferences
    
    def _should_send_notification(
        self,
        preferences: NotificationPreferences,
        notification_type: NotificationType
    ) -> bool:
        """Check if notification should be sent based on user preferences
        
        Validates Requirement 10.4:
        - Respects user notification preferences
        
        Args:
            preferences: User notification preferences
            notification_type: Type of notification
            
        Returns:
            True if notification should be sent, False otherwise
        """
        # Check if email notifications are enabled globally
        if not preferences.email_notifications:
            return False
        
        # Check specific notification type preferences
        if notification_type == NotificationType.FORUM_REPLY:
            return preferences.forum_notifications
        elif notification_type in [NotificationType.EVENT_REMINDER]:
            return preferences.event_notifications
        elif notification_type == NotificationType.ANNOUNCEMENT:
            return preferences.announcement_notifications
        
        # Default to True for other notification types
        return True
    
    def _create_notification_record(
        self,
        db: Session,
        user_id,
        notification_type: NotificationType,
        subject: str,
        content: str
    ) -> Notification:
        """Create a notification record in the database
        
        Args:
            db: Database session
            user_id: User ID
            notification_type: Type of notification
            subject: Notification subject
            content: Notification content
            
        Returns:
            Created Notification object
        """
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            subject=subject,
            content=content,
            is_read=False
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification
    
    def send_forum_reply_notification(
        self,
        db: Session,
        user_id,
        topic_title: str,
        reply_author: str,
        reply_content: str
    ) -> bool:
        """Send notification when a user receives a forum reply
        
        Validates Requirement 10.2:
        - Sends email notification when member receives forum reply
        
        Args:
            db: Database session
            user_id: User ID to notify
            topic_title: Title of the forum topic
            reply_author: Name of the reply author
            reply_content: Content of the reply
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            # Get user and preferences
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"User {user_id} not found")
                return False
            
            preferences = self._get_user_preferences(db, user_id)
            
            # Check if notification should be sent
            if not self._should_send_notification(preferences, NotificationType.FORUM_REPLY):
                logger.info(f"Forum notification disabled for user {user.email}")
                return False
            
            # Create notification record
            subject = f"Nouvelle réponse sur le forum: {topic_title}"
            content = f"{reply_author} a répondu à votre sujet '{topic_title}': {reply_content[:100]}..."
            
            self._create_notification_record(
                db, user_id, NotificationType.FORUM_REPLY, subject, content
            )
            
            # Send email
            body_text = f"""
Bonjour {user.first_name},

{reply_author} a répondu à votre sujet sur le forum OPCP.

Sujet: {topic_title}
Réponse: {reply_content}

Connectez-vous pour voir la réponse complète et continuer la discussion.

Cordialement,
L'équipe OPCP
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
        .reply {{ background-color: white; padding: 15px; margin: 20px 0; border-left: 4px solid #1a1a1a; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OPCP Forum</h1>
        </div>
        <div class="content">
            <p>Bonjour {user.first_name},</p>
            <p><strong>{reply_author}</strong> a répondu à votre sujet sur le forum.</p>
            
            <div class="reply">
                <h3>{topic_title}</h3>
                <p>{reply_content}</p>
            </div>
            
            <p>Connectez-vous pour voir la réponse complète et continuer la discussion.</p>
            
            <p>Cordialement,<br>
            L'équipe OPCP</p>
        </div>
        <div class="footer">
            <p>OPCP - OVH</p>
        </div>
    </div>
</body>
</html>
"""
            
            success = self.email_service.send_email(
                to_email=user.email,
                subject=subject,
                body_text=body_text,
                body_html=body_html
            )
            
            if success:
                logger.info(f"Forum reply notification sent to {user.email}")
            else:
                logger.error(f"Failed to send forum reply notification to {user.email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending forum reply notification: {str(e)}", exc_info=True)
            return False
    
    def send_event_notification(
        self,
        db: Session,
        user_id,
        event_title: str,
        event_description: str,
        event_date: str,
        event_location: str,
        notification_type: str = "created"
    ) -> bool:
        """Send notification about an event (created, modified, or cancelled)
        
        Validates Requirement 10.3:
        - Sends email notification when event is created or modified
        
        Args:
            db: Database session
            user_id: User ID to notify
            event_title: Title of the event
            event_description: Description of the event
            event_date: Date of the event
            event_location: Location of the event
            notification_type: Type of event notification (created, modified, cancelled)
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            # Get user and preferences
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"User {user_id} not found")
                return False
            
            preferences = self._get_user_preferences(db, user_id)
            
            # Check if notification should be sent
            if not self._should_send_notification(preferences, NotificationType.EVENT_REMINDER):
                logger.info(f"Event notification disabled for user {user.email}")
                return False
            
            # Create notification record
            if notification_type == "created":
                subject = f"Nouvel événement: {event_title}"
                action = "créé"
            elif notification_type == "modified":
                subject = f"Événement modifié: {event_title}"
                action = "modifié"
            elif notification_type == "cancelled":
                subject = f"Événement annulé: {event_title}"
                action = "annulé"
            else:
                subject = f"Événement: {event_title}"
                action = "mis à jour"
            
            content = f"L'événement '{event_title}' a été {action}. Date: {event_date}, Lieu: {event_location}"
            
            self._create_notification_record(
                db, user_id, NotificationType.EVENT_REMINDER, subject, content
            )
            
            # Send email
            body_text = f"""
Bonjour {user.first_name},

Un événement OPCP a été {action}.

Titre: {event_title}
Date: {event_date}
Lieu: {event_location}
Description: {event_description}

Connectez-vous pour plus de détails et pour vous inscrire.

Cordialement,
L'équipe OPCP
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
        .event {{ background-color: white; padding: 15px; margin: 20px 0; border-left: 4px solid #1a1a1a; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OPCP Événements</h1>
        </div>
        <div class="content">
            <p>Bonjour {user.first_name},</p>
            <p>Un événement OPCP a été <strong>{action}</strong>.</p>
            
            <div class="event">
                <h3>{event_title}</h3>
                <p><strong>Date:</strong> {event_date}</p>
                <p><strong>Lieu:</strong> {event_location}</p>
                <p><strong>Description:</strong> {event_description}</p>
            </div>
            
            <p>Connectez-vous pour plus de détails et pour vous inscrire.</p>
            
            <p>Cordialement,<br>
            L'équipe OPCP</p>
        </div>
        <div class="footer">
            <p>PSMC OPCP - OVH</p>
        </div>
    </div>
</body>
</html>
"""
            
            success = self.email_service.send_email(
                to_email=user.email,
                subject=subject,
                body_text=body_text,
                body_html=body_html
            )
            
            if success:
                logger.info(f"Event notification sent to {user.email}")
            else:
                logger.error(f"Failed to send event notification to {user.email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending event notification: {str(e)}", exc_info=True)
            return False
    
    def send_announcement(
        self,
        db: Session,
        subject: str,
        content: str,
        sender_name: str = "OPCP"
    ) -> int:
        """Send announcement to all active members with notifications enabled
        
        Validates Requirement 10.5:
        - Sends announcement to all active members by email
        - Respects user notification preferences
        
        Args:
            db: Database session
            subject: Announcement subject
            content: Announcement content
            sender_name: Name of the sender (default: OPCP)
            
        Returns:
            Number of notifications sent successfully
        """
        try:
            # Get all active members
            active_members = db.query(User).filter(
                User.role.in_([UserRole.MEMBER, UserRole.ADMINISTRATOR]),
                User.is_email_verified == True
            ).all()
            
            sent_count = 0
            
            for user in active_members:
                try:
                    # Get user preferences
                    preferences = self._get_user_preferences(db, user.id)
                    
                    # Check if notification should be sent
                    if not self._should_send_notification(preferences, NotificationType.ANNOUNCEMENT):
                        logger.info(f"Announcement notification disabled for user {user.email}")
                        continue
                    
                    # Create notification record
                    self._create_notification_record(
                        db, user.id, NotificationType.ANNOUNCEMENT, subject, content
                    )
                    
                    # Send email
                    body_text = f"""
Bonjour {user.first_name},

{sender_name} vous envoie une annonce importante.

{content}

Cordialement,
L'équipe OPCP
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
        .announcement {{ background-color: white; padding: 15px; margin: 20px 0; border-left: 4px solid #1a1a1a; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OPCP Annonce</h1>
        </div>
        <div class="content">
            <p>Bonjour {user.first_name},</p>
            <p><strong>{sender_name}</strong> vous envoie une annonce importante.</p>
            
            <div class="announcement">
                <h3>{subject}</h3>
                <p>{content}</p>
            </div>
            
            <p>Cordialement,<br>
            L'équipe OPCP</p>
        </div>
        <div class="footer">
            <p>PSMC OPCP - OVH</p>
        </div>
    </div>
</body>
</html>
"""
                    
                    success = self.email_service.send_email(
                        to_email=user.email,
                        subject=f"[OPCP] {subject}",
                        body_text=body_text,
                        body_html=body_html
                    )
                    
                    if success:
                        sent_count += 1
                        logger.info(f"Announcement sent to {user.email}")
                    else:
                        logger.error(f"Failed to send announcement to {user.email}")
                        
                except Exception as e:
                    logger.error(f"Error sending announcement to user {user.id}: {str(e)}")
                    continue
            
            logger.info(f"Announcement sent to {sent_count}/{len(active_members)} members")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error sending announcement: {str(e)}", exc_info=True)
            return 0


# Global notification service instance
notification_service = NotificationService()

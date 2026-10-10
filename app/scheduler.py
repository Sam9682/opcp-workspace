"""Background task scheduler for OPCP application
Feature: OPCP-website
Validates Requirements 4.6, 6.4, 9.4
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.membership_reminder_service import membership_reminder_service
from app.services.event_reminder_service import event_reminder_service
from app.services.user_deletion_service import UserDeletionService

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Scheduler for background tasks"""
    
    def __init__(self):
        """Initialize the task scheduler"""
        self.scheduler = BackgroundScheduler()
        logger.info("Task scheduler initialized")
    
    def membership_reminder_job(self):
        """Job to process membership expiry reminders"""
        logger.info("Running membership reminder job")
        db: Session = SessionLocal()
        try:
            result = membership_reminder_service.process_expiry_reminders(db)
            logger.info(f"Membership reminder job completed: {result}")
        except Exception as e:
            logger.error(f"Error in membership reminder job: {str(e)}", exc_info=True)
        finally:
            db.close()
    
    def event_reminder_job(self):
        """Job to process event reminders
        
        Validates Requirements 6.4:
        - Checks upcoming events (7 days before)
        - Sends reminder emails to registered participants only
        """
        logger.info("Running event reminder job")
        db: Session = SessionLocal()
        try:
            result = event_reminder_service.process_event_reminders(db)
            logger.info(f"Event reminder job completed: {result}")
        except Exception as e:
            logger.error(f"Error in event reminder job: {str(e)}", exc_info=True)
        finally:
            db.close()
    
    def user_deletion_job(self):
        """Job to process scheduled user deletions
        
        Validates Requirement 9.4:
        - Processes user deletions scheduled for 30 days
        - Anonymizes personal data
        - Preserves records for legal compliance
        """
        logger.info("Running user deletion job")
        db: Session = SessionLocal()
        try:
            result = UserDeletionService.process_scheduled_deletions(db)
            logger.info(f"User deletion job completed: processed {result} users")
        except Exception as e:
            logger.error(f"Error in user deletion job: {str(e)}", exc_info=True)
        finally:
            db.close()
    
    def start(self):
        """Start the scheduler with all configured jobs"""
        # Run membership reminder check daily at 9:00 AM
        self.scheduler.add_job(
            self.membership_reminder_job,
            trigger=CronTrigger(hour=9, minute=0),
            id='membership_reminder',
            name='Check and send membership expiry reminders',
            replace_existing=True
        )
        
        # Run event reminder check daily at 9:00 AM
        self.scheduler.add_job(
            self.event_reminder_job,
            trigger=CronTrigger(hour=9, minute=0),
            id='event_reminder',
            name='Check and send event reminders',
            replace_existing=True
        )
        
        # Run user deletion check daily at 2:00 AM
        self.scheduler.add_job(
            self.user_deletion_job,
            trigger=CronTrigger(hour=2, minute=0),
            id='user_deletion',
            name='Process scheduled user deletions',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Task scheduler started")
    
    def shutdown(self):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Task scheduler shutdown")


# Global scheduler instance
task_scheduler = TaskScheduler()

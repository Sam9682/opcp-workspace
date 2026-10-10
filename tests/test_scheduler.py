"""Tests for background task scheduler
Feature: OPCP-website
Validates Requirements 4.6, 6.4
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from apscheduler.triggers.cron import CronTrigger

from app.scheduler import TaskScheduler


class TestTaskScheduler:
    """Test suite for task scheduler"""
    
    def test_scheduler_initializes_successfully(self):
        """Test that scheduler can be initialized"""
        scheduler = TaskScheduler()
        assert scheduler.scheduler is not None
        assert not scheduler.scheduler.running
    
    @patch('app.scheduler.membership_reminder_service')
    @patch('app.scheduler.SessionLocal')
    def test_membership_reminder_job_processes_reminders(self, mock_session_local, mock_reminder_service):
        """Test that membership reminder job calls the service correctly"""
        # Setup
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_reminder_service.process_expiry_reminders.return_value = {
            'total': 5,
            'sent': 5,
            'failed': 0
        }
        
        scheduler = TaskScheduler()
        
        # Test
        scheduler.membership_reminder_job()
        
        # Verify
        mock_reminder_service.process_expiry_reminders.assert_called_once_with(mock_db)
        mock_db.close.assert_called_once()
    
    @patch('app.scheduler.membership_reminder_service')
    @patch('app.scheduler.SessionLocal')
    def test_membership_reminder_job_closes_db_on_error(self, mock_session_local, mock_reminder_service):
        """Test that database session is closed even when job fails"""
        # Setup
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_reminder_service.process_expiry_reminders.side_effect = Exception("Test error")
        
        scheduler = TaskScheduler()
        
        # Test - should not raise exception
        scheduler.membership_reminder_job()
        
        # Verify database was closed
        mock_db.close.assert_called_once()
    
    @patch('app.scheduler.event_reminder_service')
    @patch('app.scheduler.SessionLocal')
    def test_event_reminder_job_processes_reminders(self, mock_session_local, mock_reminder_service):
        """Test that event reminder job calls the service correctly
        
        Validates Requirements 6.4:
        - Background task checks upcoming events
        - Sends reminders to registered participants
        """
        # Setup
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_reminder_service.process_event_reminders.return_value = {
            'events': 2,
            'participants': 5,
            'sent': 5,
            'failed': 0
        }
        
        scheduler = TaskScheduler()
        
        # Test
        scheduler.event_reminder_job()
        
        # Verify
        mock_reminder_service.process_event_reminders.assert_called_once_with(mock_db)
        mock_db.close.assert_called_once()
    
    @patch('app.scheduler.event_reminder_service')
    @patch('app.scheduler.SessionLocal')
    def test_event_reminder_job_closes_db_on_error(self, mock_session_local, mock_reminder_service):
        """Test that database session is closed even when event reminder job fails"""
        # Setup
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_reminder_service.process_event_reminders.side_effect = Exception("Test error")
        
        scheduler = TaskScheduler()
        
        # Test - should not raise exception
        scheduler.event_reminder_job()
        
        # Verify database was closed
        mock_db.close.assert_called_once()
    
    def test_scheduler_start_adds_membership_reminder_job(self):
        """Test that starting scheduler adds the membership reminder job"""
        scheduler = TaskScheduler()
        
        # Start scheduler
        scheduler.start()
        
        try:
            # Verify scheduler is running
            assert scheduler.scheduler.running
            
            # Verify jobs were added
            jobs = scheduler.scheduler.get_jobs()
            assert len(jobs) == 2  # membership_reminder and event_reminder
            
            job_ids = [job.id for job in jobs]
            assert 'membership_reminder' in job_ids
            assert 'event_reminder' in job_ids
        finally:
            # Cleanup
            scheduler.shutdown()
    
    def test_scheduler_job_runs_daily_at_9am(self):
        """Test that jobs are scheduled to run daily at 9:00 AM"""
        scheduler = TaskScheduler()
        scheduler.start()
        
        try:
            # Get the jobs
            jobs = scheduler.scheduler.get_jobs()
            
            # Verify both jobs have CronTrigger scheduled for 9 AM
            for job in jobs:
                trigger = job.trigger
                assert trigger.__class__.__name__ == 'CronTrigger'
                
                # Verify schedule (hour=9, minute=0)
                trigger_str = str(trigger)
                assert '9' in trigger_str  # Hour 9
        finally:
            scheduler.shutdown()
    
    def test_scheduler_shutdown_stops_scheduler(self):
        """Test that shutdown stops the scheduler"""
        scheduler = TaskScheduler()
        scheduler.start()
        
        assert scheduler.scheduler.running
        
        scheduler.shutdown()
        
        assert not scheduler.scheduler.running
    
    def test_scheduler_shutdown_when_not_running(self):
        """Test that shutdown can be called when scheduler is not running"""
        scheduler = TaskScheduler()
        
        # Should not raise exception
        scheduler.shutdown()
        
        assert not scheduler.scheduler.running
    
    def test_scheduler_job_replaces_existing_job(self):
        """Test that starting scheduler replaces existing job with same ID"""
        scheduler = TaskScheduler()
        
        # Start once
        scheduler.start()
        
        try:
            # Get initial job count
            jobs = scheduler.scheduler.get_jobs()
            assert len(jobs) == 2  # membership_reminder and event_reminder
            
            # Add the membership job again (while scheduler is running)
            # This should replace the existing job
            scheduler.scheduler.add_job(
                scheduler.membership_reminder_job,
                trigger=CronTrigger(hour=9, minute=0),
                id='membership_reminder',
                name='Check and send membership expiry reminders',
                replace_existing=True
            )
            
            # Should still have only two jobs
            jobs = scheduler.scheduler.get_jobs()
            assert len(jobs) == 2
            
            job_ids = [job.id for job in jobs]
            assert 'membership_reminder' in job_ids
            assert 'event_reminder' in job_ids
        finally:
            scheduler.shutdown()

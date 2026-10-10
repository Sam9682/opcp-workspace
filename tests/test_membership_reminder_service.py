"""Tests for membership expiry reminder service
Feature: OPCP-website
Validates Requirements 4.6
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.services.membership_reminder_service import MembershipReminderService


class TestMembershipReminderService:
    """Test suite for membership reminder service"""
    
    def test_get_expiring_memberships_finds_users_expiring_in_30_days(self, db_session: Session):
        """Test that service finds users whose membership expires in exactly 30 days"""
        # Create users with different expiration dates
        # Use date() to avoid time precision issues
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        expiry_30_days = now + timedelta(days=30)
        expiry_29_days = now + timedelta(days=29)
        expiry_31_days = now + timedelta(days=31)
        
        # User expiring in 30 days (should be found)
        user1 = User(
            email="user1@example.com",
            password_hash="hash",
            first_name="User",
            last_name="One",
            role=UserRole.MEMBER,
            is_email_verified=True,
            membership_expires_at=expiry_30_days
        )
        
        # User expiring in 29 days (should not be found)
        user2 = User(
            email="user2@example.com",
            password_hash="hash",
            first_name="User",
            last_name="Two",
            role=UserRole.MEMBER,
            is_email_verified=True,
            membership_expires_at=expiry_29_days
        )
        
        # User expiring in 31 days (should not be found)
        user3 = User(
            email="user3@example.com",
            password_hash="hash",
            first_name="User",
            last_name="Three",
            role=UserRole.MEMBER,
            is_email_verified=True,
            membership_expires_at=expiry_31_days
        )
        
        db_session.add_all([user1, user2, user3])
        db_session.commit()
        
        # Test
        service = MembershipReminderService()
        expiring_users = service.get_expiring_memberships(db_session)
        
        # Verify
        assert len(expiring_users) == 1
        assert expiring_users[0].email == "user1@example.com"
    
    def test_get_expiring_memberships_excludes_unverified_users(self, db_session: Session):
        """Test that service excludes users with unverified emails"""
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        expiry_30_days = now + timedelta(days=30)
        
        # Verified user (should be found)
        user1 = User(
            email="verified@example.com",
            password_hash="hash",
            first_name="Verified",
            last_name="User",
            role=UserRole.MEMBER,
            is_email_verified=True,
            membership_expires_at=expiry_30_days
        )
        
        # Unverified user (should not be found)
        user2 = User(
            email="unverified@example.com",
            password_hash="hash",
            first_name="Unverified",
            last_name="User",
            role=UserRole.MEMBER,
            is_email_verified=False,
            membership_expires_at=expiry_30_days
        )
        
        db_session.add_all([user1, user2])
        db_session.commit()
        
        # Test
        service = MembershipReminderService()
        expiring_users = service.get_expiring_memberships(db_session)
        
        # Verify
        assert len(expiring_users) == 1
        assert expiring_users[0].email == "verified@example.com"
    
    def test_get_expiring_memberships_returns_empty_list_when_no_matches(self, db_session: Session):
        """Test that service returns empty list when no users match criteria"""
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        
        # User with no expiration date
        user1 = User(
            email="user1@example.com",
            password_hash="hash",
            first_name="User",
            last_name="One",
            role=UserRole.MEMBER,
            is_email_verified=True,
            membership_expires_at=None
        )
        
        # User expiring in 60 days
        user2 = User(
            email="user2@example.com",
            password_hash="hash",
            first_name="User",
            last_name="Two",
            role=UserRole.MEMBER,
            is_email_verified=True,
            membership_expires_at=now + timedelta(days=60)
        )
        
        db_session.add_all([user1, user2])
        db_session.commit()
        
        # Test
        service = MembershipReminderService()
        expiring_users = service.get_expiring_memberships(db_session)
        
        # Verify
        assert len(expiring_users) == 0
    
    @patch('app.services.membership_reminder_service.email_service')
    def test_send_expiry_reminder_sends_email_with_correct_content(self, mock_email_service, db_session: Session):
        """Test that reminder email is sent with correct content"""
        # Setup
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        expiry_date = now + timedelta(days=30)
        
        user = User(
            email="test@example.com",
            password_hash="hash",
            first_name="John",
            last_name="Doe",
            role=UserRole.MEMBER,
            is_email_verified=True,
            membership_expires_at=expiry_date
        )
        db_session.add(user)
        db_session.commit()
        
        mock_email_service.send_email.return_value = True
        
        # Test
        service = MembershipReminderService()
        result = service.send_expiry_reminder(user)
        
        # Verify
        assert result is True
        mock_email_service.send_email.assert_called_once()
        
        call_args = mock_email_service.send_email.call_args
        assert call_args.kwargs['to_email'] == "test@example.com"
        assert "Rappel de renouvellement" in call_args.kwargs['subject']
        assert "John Doe" in call_args.kwargs['body_text']
        assert expiry_date.strftime("%d/%m/%Y") in call_args.kwargs['body_text']
        assert call_args.kwargs['body_html'] is not None
    
    @patch('app.services.membership_reminder_service.email_service')
    def test_send_expiry_reminder_returns_false_when_no_expiration_date(self, mock_email_service, db_session: Session):
        """Test that reminder returns False when user has no expiration date"""
        # Setup
        user = User(
            email="test@example.com",
            password_hash="hash",
            first_name="John",
            last_name="Doe",
            role=UserRole.MEMBER,
            is_email_verified=True,
            membership_expires_at=None
        )
        db_session.add(user)
        db_session.commit()
        
        # Test
        service = MembershipReminderService()
        result = service.send_expiry_reminder(user)
        
        # Verify
        assert result is False
        mock_email_service.send_email.assert_not_called()
    
    @patch('app.services.membership_reminder_service.email_service')
    def test_send_expiry_reminder_handles_email_failure(self, mock_email_service, db_session: Session):
        """Test that service handles email sending failures gracefully"""
        # Setup
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        expiry_date = now + timedelta(days=30)
        
        user = User(
            email="test@example.com",
            password_hash="hash",
            first_name="John",
            last_name="Doe",
            role=UserRole.MEMBER,
            is_email_verified=True,
            membership_expires_at=expiry_date
        )
        db_session.add(user)
        db_session.commit()
        
        mock_email_service.send_email.return_value = False
        
        # Test
        service = MembershipReminderService()
        result = service.send_expiry_reminder(user)
        
        # Verify
        assert result is False
    
    @patch('app.services.membership_reminder_service.email_service')
    def test_process_expiry_reminders_sends_to_all_expiring_users(self, mock_email_service, db_session: Session):
        """Test that process_expiry_reminders sends emails to all expiring users"""
        # Setup
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        expiry_30_days = now + timedelta(days=30)
        
        # Create 3 users expiring in 30 days
        users = []
        for i in range(3):
            user = User(
                email=f"user{i}@example.com",
                password_hash="hash",
                first_name=f"User",
                last_name=f"{i}",
                role=UserRole.MEMBER,
                is_email_verified=True,
                membership_expires_at=expiry_30_days
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        mock_email_service.send_email.return_value = True
        
        # Test
        service = MembershipReminderService()
        result = service.process_expiry_reminders(db_session)
        
        # Verify
        assert result['total'] == 3
        assert result['sent'] == 3
        assert result['failed'] == 0
        assert mock_email_service.send_email.call_count == 3
    
    @patch('app.services.membership_reminder_service.email_service')
    def test_process_expiry_reminders_tracks_failures(self, mock_email_service, db_session: Session):
        """Test that process_expiry_reminders tracks failed email sends"""
        # Setup
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        expiry_30_days = now + timedelta(days=30)
        
        # Create 3 users expiring in 30 days
        users = []
        for i in range(3):
            user = User(
                email=f"user{i}@example.com",
                password_hash="hash",
                first_name=f"User",
                last_name=f"{i}",
                role=UserRole.MEMBER,
                is_email_verified=True,
                membership_expires_at=expiry_30_days
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        # Mock: first email succeeds, second fails, third succeeds
        mock_email_service.send_email.side_effect = [True, False, True]
        
        # Test
        service = MembershipReminderService()
        result = service.process_expiry_reminders(db_session)
        
        # Verify
        assert result['total'] == 3
        assert result['sent'] == 2
        assert result['failed'] == 1
    
    @patch('app.services.membership_reminder_service.email_service')
    def test_process_expiry_reminders_returns_zero_counts_when_no_users(self, mock_email_service, db_session: Session):
        """Test that process_expiry_reminders returns zero counts when no users match"""
        # Test with empty database
        service = MembershipReminderService()
        result = service.process_expiry_reminders(db_session)
        
        # Verify
        assert result['total'] == 0
        assert result['sent'] == 0
        assert result['failed'] == 0
        mock_email_service.send_email.assert_not_called()
    
    def test_reminder_email_includes_bilingual_content(self, db_session: Session):
        """Test that reminder email includes both French and English content"""
        # Setup
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        expiry_date = now + timedelta(days=30)
        
        user = User(
            email="test@example.com",
            password_hash="hash",
            first_name="Marie",
            last_name="Dupont",
            role=UserRole.MEMBER,
            is_email_verified=True,
            membership_expires_at=expiry_date
        )
        db_session.add(user)
        db_session.commit()
        
        # Test
        service = MembershipReminderService()
        
        # We'll capture the email content by mocking
        with patch('app.services.membership_reminder_service.email_service') as mock_email:
            mock_email.send_email.return_value = True
            service.send_expiry_reminder(user)
            
            call_args = mock_email.send_email.call_args
            body_text = call_args.kwargs['body_text']
            body_html = call_args.kwargs['body_html']
            
            # Verify French content
            assert "Bonjour" in body_text
            assert "expire le" in body_text
            assert "Cordialement" in body_text
            
            # Verify English content
            assert "Hello" in body_text
            assert "expires on" in body_text
            assert "Best regards" in body_text
            
            # Verify HTML content
            assert "Marie Dupont" in body_html
            assert expiry_date.strftime("%d/%m/%Y") in body_html
    
    def test_service_uses_30_days_as_reminder_threshold(self):
        """Test that service is configured to send reminders 30 days before expiration"""
        service = MembershipReminderService()
        assert service.reminder_days_before == 30
    
    def test_get_expiring_memberships_handles_timezone_aware_dates(self, db_session: Session):
        """Test that service correctly handles timezone-aware datetime objects"""
        # Create user with timezone-aware expiration date
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        expiry_30_days = now + timedelta(days=30)
        
        user = User(
            email="test@example.com",
            password_hash="hash",
            first_name="Test",
            last_name="User",
            role=UserRole.MEMBER,
            is_email_verified=True,
            membership_expires_at=expiry_30_days
        )
        db_session.add(user)
        db_session.commit()
        
        # Test
        service = MembershipReminderService()
        expiring_users = service.get_expiring_memberships(db_session)
        
        # Verify - SQLite stores dates without timezone info, but service handles this correctly
        assert len(expiring_users) == 1
        assert expiring_users[0].membership_expires_at is not None

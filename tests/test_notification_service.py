"""Tests for notification service

Validates Requirements 10.1, 10.2, 10.3, 10.5:
- Send forum reply notifications
- Send event notifications
- Send announcements
- Check user preferences before sending
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from app.models import (
    User, 
    UserRole, 
    NotificationPreferences, 
    Notification,
    NotificationType
)
from app.auth.password import hash_password
from app.services.notification_service import NotificationService


@pytest.fixture
def notification_service():
    """Create a notification service instance"""
    return NotificationService()


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_with_preferences(db_session: Session, test_user: User):
    """Create a test user with notification preferences"""
    preferences = NotificationPreferences(
        user_id=test_user.id,
        email_notifications=True,
        forum_notifications=True,
        event_notifications=True,
        announcement_notifications=True
    )
    db_session.add(preferences)
    db_session.commit()
    return test_user


def test_get_user_preferences_creates_defaults(
    notification_service: NotificationService,
    db_session: Session,
    test_user: User
):
    """Test that _get_user_preferences creates default preferences if none exist"""
    # Verify no preferences exist
    preferences = db_session.query(NotificationPreferences).filter(
        NotificationPreferences.user_id == test_user.id
    ).first()
    assert preferences is None
    
    # Get preferences (should create defaults)
    preferences = notification_service._get_user_preferences(db_session, test_user.id)
    
    assert preferences is not None
    assert preferences.user_id == test_user.id
    assert preferences.email_notifications is True
    assert preferences.forum_notifications is True
    assert preferences.event_notifications is True
    assert preferences.announcement_notifications is True


def test_get_user_preferences_returns_existing(
    notification_service: NotificationService,
    db_session: Session,
    test_user: User
):
    """Test that _get_user_preferences returns existing preferences"""
    # Create custom preferences
    custom_prefs = NotificationPreferences(
        user_id=test_user.id,
        email_notifications=False,
        forum_notifications=True,
        event_notifications=False,
        announcement_notifications=True
    )
    db_session.add(custom_prefs)
    db_session.commit()
    
    # Get preferences
    preferences = notification_service._get_user_preferences(db_session, test_user.id)
    
    assert preferences.user_id == test_user.id
    assert preferences.email_notifications is False
    assert preferences.forum_notifications is True
    assert preferences.event_notifications is False
    assert preferences.announcement_notifications is True


def test_should_send_notification_respects_email_disabled(
    notification_service: NotificationService
):
    """Test that notifications are not sent when email_notifications is disabled"""
    preferences = NotificationPreferences(
        user_id="test-id",
        email_notifications=False,
        forum_notifications=True,
        event_notifications=True,
        announcement_notifications=True
    )
    
    # Should not send any notification when email is disabled
    assert notification_service._should_send_notification(
        preferences, NotificationType.FORUM_REPLY
    ) is False
    assert notification_service._should_send_notification(
        preferences, NotificationType.EVENT_REMINDER
    ) is False
    assert notification_service._should_send_notification(
        preferences, NotificationType.ANNOUNCEMENT
    ) is False


def test_should_send_notification_respects_forum_preference(
    notification_service: NotificationService
):
    """Test that forum notifications respect forum_notifications preference"""
    preferences = NotificationPreferences(
        user_id="test-id",
        email_notifications=True,
        forum_notifications=False,
        event_notifications=True,
        announcement_notifications=True
    )
    
    assert notification_service._should_send_notification(
        preferences, NotificationType.FORUM_REPLY
    ) is False


def test_should_send_notification_respects_event_preference(
    notification_service: NotificationService
):
    """Test that event notifications respect event_notifications preference"""
    preferences = NotificationPreferences(
        user_id="test-id",
        email_notifications=True,
        forum_notifications=True,
        event_notifications=False,
        announcement_notifications=True
    )
    
    assert notification_service._should_send_notification(
        preferences, NotificationType.EVENT_REMINDER
    ) is False


def test_should_send_notification_respects_announcement_preference(
    notification_service: NotificationService
):
    """Test that announcements respect announcement_notifications preference"""
    preferences = NotificationPreferences(
        user_id="test-id",
        email_notifications=True,
        forum_notifications=True,
        event_notifications=True,
        announcement_notifications=False
    )
    
    assert notification_service._should_send_notification(
        preferences, NotificationType.ANNOUNCEMENT
    ) is False


def test_create_notification_record(
    notification_service: NotificationService,
    db_session: Session,
    test_user: User
):
    """Test that _create_notification_record creates a notification in the database"""
    notification = notification_service._create_notification_record(
        db_session,
        test_user.id,
        NotificationType.FORUM_REPLY,
        "Test Subject",
        "Test Content"
    )
    
    assert notification is not None
    assert notification.user_id == test_user.id
    assert notification.type == NotificationType.FORUM_REPLY
    assert notification.subject == "Test Subject"
    assert notification.content == "Test Content"
    assert notification.is_read is False
    
    # Verify it's in the database
    db_notification = db_session.query(Notification).filter(
        Notification.id == notification.id
    ).first()
    assert db_notification is not None


@patch('app.services.notification_service.email_service')
def test_send_forum_reply_notification_success(
    mock_email_service: Mock,
    notification_service: NotificationService,
    db_session: Session,
    test_user_with_preferences: User
):
    """Test sending forum reply notification successfully
    
    Validates Requirement 10.2:
    - Sends email notification when member receives forum reply
    """
    mock_email_service.send_email.return_value = True
    notification_service.email_service = mock_email_service
    
    result = notification_service.send_forum_reply_notification(
        db_session,
        test_user_with_preferences.id,
        "Test Topic",
        "John Doe",
        "This is a test reply"
    )
    
    assert result is True
    mock_email_service.send_email.assert_called_once()
    
    # Verify notification was created
    notification = db_session.query(Notification).filter(
        Notification.user_id == test_user_with_preferences.id,
        Notification.type == NotificationType.FORUM_REPLY
    ).first()
    assert notification is not None
    assert "Test Topic" in notification.subject


@patch('app.services.notification_service.email_service')
def test_send_forum_reply_notification_respects_preferences(
    mock_email_service: Mock,
    notification_service: NotificationService,
    db_session: Session,
    test_user: User
):
    """Test that forum reply notification respects user preferences
    
    Validates Requirement 10.4:
    - Checks user preferences before sending notifications
    """
    # Create preferences with forum notifications disabled
    preferences = NotificationPreferences(
        user_id=test_user.id,
        email_notifications=True,
        forum_notifications=False,
        event_notifications=True,
        announcement_notifications=True
    )
    db_session.add(preferences)
    db_session.commit()
    
    notification_service.email_service = mock_email_service
    
    result = notification_service.send_forum_reply_notification(
        db_session,
        test_user.id,
        "Test Topic",
        "John Doe",
        "This is a test reply"
    )
    
    assert result is False
    mock_email_service.send_email.assert_not_called()


@patch('app.services.notification_service.email_service')
def test_send_event_notification_success(
    mock_email_service: Mock,
    notification_service: NotificationService,
    db_session: Session,
    test_user_with_preferences: User
):
    """Test sending event notification successfully
    
    Validates Requirement 10.3:
    - Sends email notification when event is created or modified
    """
    mock_email_service.send_email.return_value = True
    notification_service.email_service = mock_email_service
    
    result = notification_service.send_event_notification(
        db_session,
        test_user_with_preferences.id,
        "Test Event",
        "This is a test event",
        "2024-12-31 18:00",
        "Paris",
        "created"
    )
    
    assert result is True
    mock_email_service.send_email.assert_called_once()
    
    # Verify notification was created
    notification = db_session.query(Notification).filter(
        Notification.user_id == test_user_with_preferences.id,
        Notification.type == NotificationType.EVENT_REMINDER
    ).first()
    assert notification is not None
    assert "Test Event" in notification.subject


@patch('app.services.notification_service.email_service')
def test_send_event_notification_respects_preferences(
    mock_email_service: Mock,
    notification_service: NotificationService,
    db_session: Session,
    test_user: User
):
    """Test that event notification respects user preferences
    
    Validates Requirement 10.4:
    - Checks user preferences before sending notifications
    """
    # Create preferences with event notifications disabled
    preferences = NotificationPreferences(
        user_id=test_user.id,
        email_notifications=True,
        forum_notifications=True,
        event_notifications=False,
        announcement_notifications=True
    )
    db_session.add(preferences)
    db_session.commit()
    
    notification_service.email_service = mock_email_service
    
    result = notification_service.send_event_notification(
        db_session,
        test_user.id,
        "Test Event",
        "This is a test event",
        "2024-12-31 18:00",
        "Paris",
        "created"
    )
    
    assert result is False
    mock_email_service.send_email.assert_not_called()


@patch('app.services.notification_service.email_service')
def test_send_announcement_to_all_active_members(
    mock_email_service: Mock,
    notification_service: NotificationService,
    db_session: Session
):
    """Test sending announcement to all active members
    
    Validates Requirement 10.5:
    - Sends announcement to all active members by email
    """
    # Create multiple users
    users = []
    for i in range(3):
        user = User(
            email=f"user{i}@example.com",
            password_hash=hash_password("Test1234"),
            first_name=f"User{i}",
            last_name="Test",
            role=UserRole.MEMBER,
            is_email_verified=True
        )
        db_session.add(user)
        users.append(user)
    db_session.commit()
    
    # Create preferences for all users
    for user in users:
        preferences = NotificationPreferences(
            user_id=user.id,
            email_notifications=True,
            forum_notifications=True,
            event_notifications=True,
            announcement_notifications=True
        )
        db_session.add(preferences)
    db_session.commit()
    
    mock_email_service.send_email.return_value = True
    notification_service.email_service = mock_email_service
    
    sent_count = notification_service.send_announcement(
        db_session,
        "Important Announcement",
        "This is an important announcement for all members"
    )
    
    assert sent_count == 3
    assert mock_email_service.send_email.call_count == 3
    
    # Verify notifications were created for all users
    for user in users:
        notification = db_session.query(Notification).filter(
            Notification.user_id == user.id,
            Notification.type == NotificationType.ANNOUNCEMENT
        ).first()
        assert notification is not None


@patch('app.services.notification_service.email_service')
def test_send_announcement_respects_preferences(
    mock_email_service: Mock,
    notification_service: NotificationService,
    db_session: Session
):
    """Test that announcements respect user preferences
    
    Validates Requirement 10.4:
    - Checks user preferences before sending announcements
    """
    # Create users with different preferences
    user1 = User(
        email="user1@example.com",
        password_hash=hash_password("Test1234"),
        first_name="User1",
        last_name="Test",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    user2 = User(
        email="user2@example.com",
        password_hash=hash_password("Test1234"),
        first_name="User2",
        last_name="Test",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add_all([user1, user2])
    db_session.commit()
    
    # User1 has announcements enabled, User2 has them disabled
    prefs1 = NotificationPreferences(
        user_id=user1.id,
        email_notifications=True,
        forum_notifications=True,
        event_notifications=True,
        announcement_notifications=True
    )
    prefs2 = NotificationPreferences(
        user_id=user2.id,
        email_notifications=True,
        forum_notifications=True,
        event_notifications=True,
        announcement_notifications=False
    )
    db_session.add_all([prefs1, prefs2])
    db_session.commit()
    
    mock_email_service.send_email.return_value = True
    notification_service.email_service = mock_email_service
    
    sent_count = notification_service.send_announcement(
        db_session,
        "Important Announcement",
        "This is an important announcement"
    )
    
    # Only user1 should receive the announcement
    assert sent_count == 1
    assert mock_email_service.send_email.call_count == 1


@patch('app.services.notification_service.email_service')
def test_send_announcement_only_to_verified_members(
    mock_email_service: Mock,
    notification_service: NotificationService,
    db_session: Session
):
    """Test that announcements are only sent to verified members
    
    Validates Requirement 10.5:
    - Only sends to active members (verified email)
    """
    # Create verified and unverified users
    verified_user = User(
        email="verified@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Verified",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    unverified_user = User(
        email="unverified@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Unverified",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=False
    )
    db_session.add_all([verified_user, unverified_user])
    db_session.commit()
    
    # Create preferences for both
    for user in [verified_user, unverified_user]:
        preferences = NotificationPreferences(
            user_id=user.id,
            email_notifications=True,
            forum_notifications=True,
            event_notifications=True,
            announcement_notifications=True
        )
        db_session.add(preferences)
    db_session.commit()
    
    mock_email_service.send_email.return_value = True
    notification_service.email_service = mock_email_service
    
    sent_count = notification_service.send_announcement(
        db_session,
        "Important Announcement",
        "This is an important announcement"
    )
    
    # Only verified user should receive the announcement
    assert sent_count == 1
    assert mock_email_service.send_email.call_count == 1


def test_send_forum_reply_notification_user_not_found(
    notification_service: NotificationService,
    db_session: Session
):
    """Test that send_forum_reply_notification handles non-existent user"""
    import uuid
    fake_user_id = uuid.uuid4()
    
    result = notification_service.send_forum_reply_notification(
        db_session,
        fake_user_id,
        "Test Topic",
        "John Doe",
        "This is a test reply"
    )
    
    assert result is False


def test_send_event_notification_user_not_found(
    notification_service: NotificationService,
    db_session: Session
):
    """Test that send_event_notification handles non-existent user"""
    import uuid
    fake_user_id = uuid.uuid4()
    
    result = notification_service.send_event_notification(
        db_session,
        fake_user_id,
        "Test Event",
        "This is a test event",
        "2024-12-31 18:00",
        "Paris",
        "created"
    )
    
    assert result is False

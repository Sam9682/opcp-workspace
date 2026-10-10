"""Tests for Notification and NotificationPreferences models"""
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.models import Notification, NotificationPreferences, NotificationType, User, UserRole


def test_create_notification(db_session):
    """Test creating a notification record"""
    # Create a user first
    user = User(
        email="user@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create a notification
    notification = Notification(
        user_id=user.id,
        type=NotificationType.FORUM_REPLY,
        subject="New reply to your post",
        content="Someone replied to your forum post",
        is_read=False
    )
    db_session.add(notification)
    db_session.commit()
    
    # Verify notification was created
    assert notification.id is not None
    assert notification.user_id == user.id
    assert notification.type == NotificationType.FORUM_REPLY
    assert notification.subject == "New reply to your post"
    assert notification.content == "Someone replied to your forum post"
    assert notification.is_read is False
    assert notification.sent_at is not None
    assert isinstance(notification.sent_at, datetime)


def test_notification_default_is_read(db_session):
    """Test that is_read defaults to False"""
    user = User(
        email="user2@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    notification = Notification(
        user_id=user.id,
        type=NotificationType.ANNOUNCEMENT,
        subject="Test",
        content="Test content"
    )
    db_session.add(notification)
    db_session.commit()
    
    assert notification.is_read is False


def test_notification_type_enum(db_session):
    """Test NotificationType enum values"""
    user = User(
        email="user3@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Test all notification types
    types = [
        NotificationType.FORUM_REPLY,
        NotificationType.EVENT_REMINDER,
        NotificationType.MEMBERSHIP_EXPIRY,
        NotificationType.ANNOUNCEMENT,
        NotificationType.PAYMENT_CONFIRMATION
    ]
    
    for notification_type in types:
        notification = Notification(
            user_id=user.id,
            type=notification_type,
            subject=f"Test {notification_type.value}",
            content="Test content"
        )
        db_session.add(notification)
        db_session.commit()
        assert notification.type == notification_type


def test_notification_user_relationship(db_session):
    """Test relationship between Notification and User"""
    user = User(
        email="user4@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    notification = Notification(
        user_id=user.id,
        type=NotificationType.EVENT_REMINDER,
        subject="Event reminder",
        content="Your event is tomorrow"
    )
    db_session.add(notification)
    db_session.commit()
    
    # Test relationship from notification to user
    assert notification.user == user
    
    # Test relationship from user to notifications
    assert len(user.notifications) == 1
    assert user.notifications[0] == notification


def test_notification_user_index(db_session):
    """Test that index on user_id exists and works efficiently"""
    user = User(
        email="user5@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create multiple notifications for the user
    for i in range(5):
        notification = Notification(
            user_id=user.id,
            type=NotificationType.ANNOUNCEMENT,
            subject=f"Notification {i}",
            content=f"Content {i}"
        )
        db_session.add(notification)
    db_session.commit()
    
    # Query by user_id (should use idx_notifications_user)
    notifications = db_session.query(Notification).filter(
        Notification.user_id == user.id
    ).all()
    assert len(notifications) == 5


def test_notification_mark_as_read(db_session):
    """Test marking a notification as read"""
    user = User(
        email="user6@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    notification = Notification(
        user_id=user.id,
        type=NotificationType.FORUM_REPLY,
        subject="Test",
        content="Test content"
    )
    db_session.add(notification)
    db_session.commit()
    
    # Initially unread
    assert notification.is_read is False
    
    # Mark as read
    notification.is_read = True
    db_session.commit()
    assert notification.is_read is True


def test_notification_repr(db_session):
    """Test Notification __repr__ method"""
    user = User(
        email="user7@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    notification = Notification(
        user_id=user.id,
        type=NotificationType.ANNOUNCEMENT,
        subject="Test",
        content="Test content"
    )
    db_session.add(notification)
    db_session.commit()
    
    repr_str = repr(notification)
    assert "Notification" in repr_str
    assert str(notification.id) in repr_str
    assert str(user.id) in repr_str
    assert "ANNOUNCEMENT" in repr_str


def test_create_notification_preferences(db_session):
    """Test creating notification preferences"""
    user = User(
        email="user8@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create notification preferences
    prefs = NotificationPreferences(
        user_id=user.id,
        email_notifications=True,
        forum_notifications=True,
        event_notifications=False,
        announcement_notifications=True
    )
    db_session.add(prefs)
    db_session.commit()
    
    # Verify preferences were created
    assert prefs.user_id == user.id
    assert prefs.email_notifications is True
    assert prefs.forum_notifications is True
    assert prefs.event_notifications is False
    assert prefs.announcement_notifications is True


def test_notification_preferences_defaults(db_session):
    """Test that notification preferences default to True"""
    user = User(
        email="user9@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    prefs = NotificationPreferences(
        user_id=user.id
    )
    db_session.add(prefs)
    db_session.commit()
    
    assert prefs.email_notifications is True
    assert prefs.forum_notifications is True
    assert prefs.event_notifications is True
    assert prefs.announcement_notifications is True


def test_notification_preferences_user_relationship(db_session):
    """Test relationship between NotificationPreferences and User"""
    user = User(
        email="user10@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    prefs = NotificationPreferences(
        user_id=user.id
    )
    db_session.add(prefs)
    db_session.commit()
    
    # Test relationship from preferences to user
    assert prefs.user == user
    
    # Test relationship from user to preferences
    assert user.notification_preferences == prefs


def test_notification_preferences_unique_per_user(db_session):
    """Test that each user can only have one set of preferences"""
    user = User(
        email="user11@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create first preferences
    prefs1 = NotificationPreferences(
        user_id=user.id
    )
    db_session.add(prefs1)
    db_session.commit()
    
    # Try to create duplicate preferences
    prefs2 = NotificationPreferences(
        user_id=user.id
    )
    db_session.add(prefs2)
    
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_notification_preferences_update(db_session):
    """Test updating notification preferences"""
    user = User(
        email="user12@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    prefs = NotificationPreferences(
        user_id=user.id
    )
    db_session.add(prefs)
    db_session.commit()
    
    # Update preferences
    prefs.email_notifications = False
    prefs.forum_notifications = False
    db_session.commit()
    
    # Verify updates
    assert prefs.email_notifications is False
    assert prefs.forum_notifications is False
    assert prefs.event_notifications is True
    assert prefs.announcement_notifications is True


def test_notification_preferences_repr(db_session):
    """Test NotificationPreferences __repr__ method"""
    user = User(
        email="user13@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    prefs = NotificationPreferences(
        user_id=user.id
    )
    db_session.add(prefs)
    db_session.commit()
    
    repr_str = repr(prefs)
    assert "NotificationPreferences" in repr_str
    assert str(user.id) in repr_str


def test_notification_cascade_delete(db_session):
    """Test that deleting a user cascades to notifications"""
    user = User(
        email="user14@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    notification = Notification(
        user_id=user.id,
        type=NotificationType.ANNOUNCEMENT,
        subject="Test",
        content="Test content"
    )
    db_session.add(notification)
    db_session.commit()
    
    notification_id = notification.id
    
    # Delete user
    db_session.delete(user)
    db_session.commit()
    
    # Verify notification was also deleted
    deleted_notification = db_session.query(Notification).filter(
        Notification.id == notification_id
    ).first()
    assert deleted_notification is None


def test_notification_preferences_cascade_delete(db_session):
    """Test that deleting a user cascades to notification preferences"""
    user = User(
        email="user15@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    prefs = NotificationPreferences(
        user_id=user.id
    )
    db_session.add(prefs)
    db_session.commit()
    
    user_id = user.id
    
    # Delete user
    db_session.delete(user)
    db_session.commit()
    
    # Verify preferences were also deleted
    deleted_prefs = db_session.query(NotificationPreferences).filter(
        NotificationPreferences.user_id == user_id
    ).first()
    assert deleted_prefs is None

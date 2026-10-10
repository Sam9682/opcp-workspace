"""Tests for notification preferences endpoints

Validates Requirement 10.4:
- GET /api/notifications/preferences endpoint
- PUT /api/notifications/preferences endpoint
- Store and retrieve user notification preferences
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import User, UserRole, NotificationPreferences
from app.auth.password import hash_password
from app.auth.token import create_access_token


def test_get_notification_preferences_creates_defaults(
    client: TestClient,
    db_session: Session
):
    """Test that GET /api/notifications/preferences creates default preferences if none exist"""
    # Create a test user
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
    
    # Generate token
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role.value})
    
    # Get preferences (should create defaults)
    response = client.get(
        "/api/notifications/preferences",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user.id)
    assert data["email_notifications"] is True
    assert data["forum_notifications"] is True
    assert data["event_notifications"] is True
    assert data["announcement_notifications"] is True
    
    # Verify preferences were created in database
    preferences = db_session.query(NotificationPreferences).filter(
        NotificationPreferences.user_id == user.id
    ).first()
    assert preferences is not None
    assert preferences.email_notifications is True


def test_get_notification_preferences_returns_existing(
    client: TestClient,
    db_session: Session
):
    """Test that GET /api/notifications/preferences returns existing preferences"""
    # Create a test user
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
    
    # Create custom preferences
    preferences = NotificationPreferences(
        user_id=user.id,
        email_notifications=False,
        forum_notifications=True,
        event_notifications=False,
        announcement_notifications=True
    )
    db_session.add(preferences)
    db_session.commit()
    
    # Generate token
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role.value})
    
    # Get preferences
    response = client.get(
        "/api/notifications/preferences",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user.id)
    assert data["email_notifications"] is False
    assert data["forum_notifications"] is True
    assert data["event_notifications"] is False
    assert data["announcement_notifications"] is True


def test_get_notification_preferences_requires_authentication(
    client: TestClient
):
    """Test that GET /api/notifications/preferences requires authentication"""
    response = client.get("/api/notifications/preferences")
    
    assert response.status_code == 403  # No credentials provided


def test_update_notification_preferences_creates_new(
    client: TestClient,
    db_session: Session
):
    """Test that PUT /api/notifications/preferences creates new preferences if none exist"""
    # Create a test user
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
    
    # Generate token
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role.value})
    
    # Update preferences (should create new)
    response = client.put(
        "/api/notifications/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email_notifications": False,
            "forum_notifications": True,
            "event_notifications": False,
            "announcement_notifications": True
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user.id)
    assert data["email_notifications"] is False
    assert data["forum_notifications"] is True
    assert data["event_notifications"] is False
    assert data["announcement_notifications"] is True
    
    # Verify preferences were created in database
    preferences = db_session.query(NotificationPreferences).filter(
        NotificationPreferences.user_id == user.id
    ).first()
    assert preferences is not None
    assert preferences.email_notifications is False
    assert preferences.forum_notifications is True


def test_update_notification_preferences_updates_existing(
    client: TestClient,
    db_session: Session
):
    """Test that PUT /api/notifications/preferences updates existing preferences"""
    # Create a test user
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
    
    # Create initial preferences
    preferences = NotificationPreferences(
        user_id=user.id,
        email_notifications=True,
        forum_notifications=True,
        event_notifications=True,
        announcement_notifications=True
    )
    db_session.add(preferences)
    db_session.commit()
    
    # Generate token
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role.value})
    
    # Update preferences
    response = client.put(
        "/api/notifications/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email_notifications": False,
            "event_notifications": False
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user.id)
    assert data["email_notifications"] is False
    assert data["forum_notifications"] is True  # Unchanged
    assert data["event_notifications"] is False
    assert data["announcement_notifications"] is True  # Unchanged
    
    # Verify preferences were updated in database
    db_session.refresh(preferences)
    assert preferences.email_notifications is False
    assert preferences.forum_notifications is True
    assert preferences.event_notifications is False
    assert preferences.announcement_notifications is True


def test_update_notification_preferences_partial_update(
    client: TestClient,
    db_session: Session
):
    """Test that PUT /api/notifications/preferences allows partial updates"""
    # Create a test user
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
    
    # Create initial preferences
    preferences = NotificationPreferences(
        user_id=user.id,
        email_notifications=True,
        forum_notifications=True,
        event_notifications=True,
        announcement_notifications=True
    )
    db_session.add(preferences)
    db_session.commit()
    
    # Generate token
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role.value})
    
    # Update only one preference
    response = client.put(
        "/api/notifications/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "forum_notifications": False
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["email_notifications"] is True  # Unchanged
    assert data["forum_notifications"] is False  # Updated
    assert data["event_notifications"] is True  # Unchanged
    assert data["announcement_notifications"] is True  # Unchanged


def test_update_notification_preferences_requires_authentication(
    client: TestClient
):
    """Test that PUT /api/notifications/preferences requires authentication"""
    response = client.put(
        "/api/notifications/preferences",
        json={
            "email_notifications": False
        }
    )
    
    assert response.status_code == 403  # No credentials provided


def test_notification_preferences_persistence(
    client: TestClient,
    db_session: Session
):
    """Test that notification preferences persist across multiple requests"""
    # Create a test user
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
    
    # Generate token
    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role.value})
    
    # Set preferences
    response1 = client.put(
        "/api/notifications/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email_notifications": False,
            "forum_notifications": False,
            "event_notifications": False,
            "announcement_notifications": False
        }
    )
    assert response1.status_code == 200
    
    # Get preferences in a new request
    response2 = client.get(
        "/api/notifications/preferences",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response2.status_code == 200
    data = response2.json()
    assert data["email_notifications"] is False
    assert data["forum_notifications"] is False
    assert data["event_notifications"] is False
    assert data["announcement_notifications"] is False

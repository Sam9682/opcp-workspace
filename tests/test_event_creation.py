"""Tests for event creation endpoint
Feature: OPCP-website
Validates Requirements 6.2, 10.3
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from app.models import User, UserRole, Event, EventStatus, NotificationPreferences


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for tests"""
    from app.auth.password import hash_password
    
    user = User(
        email="admin@example.com",
        password_hash=hash_password("AdminPass123"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(admin_user):
    """Create authentication headers with admin JWT token"""
    from app.auth.token import create_access_token
    
    token = create_access_token({"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def member_user(db_session):
    """Create a regular member user for tests"""
    from app.auth.password import hash_password
    
    user = User(
        email="member@example.com",
        password_hash=hash_password("MemberPass123"),
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def member_headers(member_user):
    """Create authentication headers with member JWT token"""
    from app.auth.token import create_access_token
    
    token = create_access_token({"sub": str(member_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def valid_event_data():
    """Create valid event data for tests"""
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    
    return {
        "title": "Assemblée Générale 2026",
        "description": "Assemblée générale annuelle de l'PSMC",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "location": "Salle des fêtes, 123 Rue de Paris",
        "max_participants": 50
    }


def test_create_event_success(client, admin_headers, valid_event_data, db_session):
    """Test successful event creation by admin
    
    Validates Requirements 6.2:
    - Creates event with validated data
    - Stores event with all details
    """
    with patch('app.events.router.email_service.send_email') as mock_send_email:
        mock_send_email.return_value = True
        
        response = client.post(
            "/api/events",
            json=valid_event_data,
            headers=admin_headers
        )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["success"] is True
    assert "Event created successfully" in data["message"]
    assert data["event"]["title"] == valid_event_data["title"]
    assert data["event"]["description"] == valid_event_data["description"]
    assert data["event"]["location"] == valid_event_data["location"]
    assert data["event"]["max_participants"] == valid_event_data["max_participants"]
    assert data["event"]["status"] == "scheduled"
    assert "id" in data["event"]
    assert "created_by" in data["event"]
    
    # Verify event was stored in database
    event = db_session.query(Event).filter(Event.title == valid_event_data["title"]).first()
    assert event is not None
    assert event.title == valid_event_data["title"]
    assert event.description == valid_event_data["description"]
    assert event.location == valid_event_data["location"]
    assert event.max_participants == valid_event_data["max_participants"]
    assert event.status == EventStatus.SCHEDULED


def test_create_event_sends_notifications(client, admin_headers, valid_event_data, db_session, admin_user):
    """Test that event creation sends notifications to all members
    
    Validates Requirements 10.3:
    - Sends notification to all members when event is created
    """
    # Create additional members with notification preferences
    from app.auth.password import hash_password
    
    member1 = User(
        email="member1@example.com",
        password_hash=hash_password("Pass123"),
        first_name="Member",
        last_name="One",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    member2 = User(
        email="member2@example.com",
        password_hash=hash_password("Pass123"),
        first_name="Member",
        last_name="Two",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add_all([member1, member2])
    db_session.commit()
    
    # Create notification preferences (event notifications enabled)
    prefs1 = NotificationPreferences(
        user_id=member1.id,
        event_notifications=True
    )
    prefs2 = NotificationPreferences(
        user_id=member2.id,
        event_notifications=True
    )
    db_session.add_all([prefs1, prefs2])
    db_session.commit()
    
    with patch('app.events.router.email_service.send_email') as mock_send_email:
        mock_send_email.return_value = True
        
        response = client.post(
            "/api/events",
            json=valid_event_data,
            headers=admin_headers
        )
    
    assert response.status_code == 201
    data = response.json()
    
    # Verify notifications were sent (should be 2: member1 and member2, not admin)
    assert "2 members" in data["message"]
    assert mock_send_email.call_count == 2
    
    # Verify email content
    calls = mock_send_email.call_args_list
    emails_sent_to = [call[1]['to_email'] for call in calls]
    assert "member1@example.com" in emails_sent_to
    assert "member2@example.com" in emails_sent_to
    assert "admin@example.com" not in emails_sent_to  # Admin shouldn't receive notification


def test_create_event_respects_notification_preferences(client, admin_headers, valid_event_data, db_session):
    """Test that notifications respect user preferences
    
    Validates Requirements 10.3:
    - Only sends notifications to members with event notifications enabled
    """
    from app.auth.password import hash_password
    
    # Create member with notifications enabled
    member_enabled = User(
        email="enabled@example.com",
        password_hash=hash_password("Pass123"),
        first_name="Enabled",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    # Create member with notifications disabled
    member_disabled = User(
        email="disabled@example.com",
        password_hash=hash_password("Pass123"),
        first_name="Disabled",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add_all([member_enabled, member_disabled])
    db_session.commit()
    
    # Set notification preferences
    prefs_enabled = NotificationPreferences(
        user_id=member_enabled.id,
        event_notifications=True
    )
    prefs_disabled = NotificationPreferences(
        user_id=member_disabled.id,
        event_notifications=False
    )
    db_session.add_all([prefs_enabled, prefs_disabled])
    db_session.commit()
    
    with patch('app.events.router.email_service.send_email') as mock_send_email:
        mock_send_email.return_value = True
        
        response = client.post(
            "/api/events",
            json=valid_event_data,
            headers=admin_headers
        )
    
    assert response.status_code == 201
    
    # Verify only one notification was sent (to member_enabled)
    assert mock_send_email.call_count == 1
    call_args = mock_send_email.call_args_list[0]
    assert call_args[1]['to_email'] == "enabled@example.com"


def test_create_event_non_admin_forbidden(client, member_headers, valid_event_data):
    """Test that non-admin users cannot create events
    
    Validates Requirements 7.2:
    - Restricts administrative functions to users with administrator role
    """
    response = client.post(
        "/api/events",
        json=valid_event_data,
        headers=member_headers
    )
    
    assert response.status_code == 403
    data = response.json()
    # The detail field contains the ErrorResponse structure with nested error
    assert "detail" in data
    detail = data["detail"]
    assert "error" in detail
    error = detail["error"]
    assert error["code"] == "INSUFFICIENT_PERMISSIONS"
    assert "Administrator role required" in error["message"]


def test_create_event_unauthenticated(client, valid_event_data):
    """Test that unauthenticated users cannot create events"""
    response = client.post(
        "/api/events",
        json=valid_event_data
    )
    
    assert response.status_code == 403  # FastAPI HTTPBearer returns 403 for missing auth


def test_create_event_invalid_dates(client, admin_headers, valid_event_data):
    """Test event creation with invalid dates
    
    Validates Requirements 6.2:
    - Validates event data (dates must be valid)
    """
    # Test end_date before start_date
    invalid_data = valid_event_data.copy()
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    invalid_data["start_date"] = start_date.isoformat()
    invalid_data["end_date"] = (start_date - timedelta(hours=1)).isoformat()
    
    response = client.post(
        "/api/events",
        json=invalid_data,
        headers=admin_headers
    )
    
    assert response.status_code == 422  # Pydantic validation error
    data = response.json()
    assert "detail" in data


def test_create_event_past_date(client, admin_headers, valid_event_data):
    """Test event creation with past date
    
    Validates Requirements 6.2:
    - Validates that event dates are in the future
    """
    invalid_data = valid_event_data.copy()
    past_date = datetime.now(timezone.utc) - timedelta(days=1)
    invalid_data["start_date"] = past_date.isoformat()
    invalid_data["end_date"] = (past_date + timedelta(hours=2)).isoformat()
    
    response = client.post(
        "/api/events",
        json=invalid_data,
        headers=admin_headers
    )
    
    assert response.status_code == 422  # Pydantic validation error


def test_create_event_missing_required_fields(client, admin_headers):
    """Test event creation with missing required fields
    
    Validates Requirements 6.2:
    - Validates that required event data is provided
    """
    # Missing title
    response = client.post(
        "/api/events",
        json={
            "description": "Test event",
            "start_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "end_date": (datetime.now(timezone.utc) + timedelta(days=7, hours=2)).isoformat()
        },
        headers=admin_headers
    )
    
    assert response.status_code == 422


def test_create_event_optional_fields(client, admin_headers, db_session):
    """Test event creation with only required fields
    
    Validates Requirements 6.2:
    - Optional fields (description, location, max_participants) can be omitted
    """
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    
    minimal_data = {
        "title": "Minimal Event",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
    
    with patch('app.events.router.email_service.send_email') as mock_send_email:
        mock_send_email.return_value = True
        
        response = client.post(
            "/api/events",
            json=minimal_data,
            headers=admin_headers
        )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["event"]["title"] == "Minimal Event"
    assert data["event"]["description"] is None
    assert data["event"]["location"] is None
    assert data["event"]["max_participants"] is None


def test_create_event_email_failure_does_not_prevent_creation(client, admin_headers, valid_event_data, db_session):
    """Test that email failures don't prevent event creation
    
    Validates Requirements 6.2:
    - Event is created even if email notifications fail
    """
    with patch('app.events.router.email_service.send_email') as mock_send_email:
        mock_send_email.return_value = False  # Simulate email failure
        
        response = client.post(
            "/api/events",
            json=valid_event_data,
            headers=admin_headers
        )
    
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    
    # Verify event was still created
    event = db_session.query(Event).filter(Event.title == valid_event_data["title"]).first()
    assert event is not None


def test_create_event_title_length_validation(client, admin_headers, valid_event_data):
    """Test event title length validation
    
    Validates Requirements 6.2:
    - Title must not exceed 255 characters
    """
    invalid_data = valid_event_data.copy()
    invalid_data["title"] = "A" * 256  # Exceeds max length
    
    response = client.post(
        "/api/events",
        json=invalid_data,
        headers=admin_headers
    )
    
    assert response.status_code == 422


def test_create_event_location_length_validation(client, admin_headers, valid_event_data):
    """Test event location length validation
    
    Validates Requirements 6.2:
    - Location must not exceed 255 characters
    """
    invalid_data = valid_event_data.copy()
    invalid_data["location"] = "A" * 256  # Exceeds max length
    
    response = client.post(
        "/api/events",
        json=invalid_data,
        headers=admin_headers
    )
    
    assert response.status_code == 422


def test_create_event_max_participants_validation(client, admin_headers, valid_event_data):
    """Test max_participants validation
    
    Validates Requirements 6.2:
    - max_participants must be positive if provided
    """
    invalid_data = valid_event_data.copy()
    invalid_data["max_participants"] = 0  # Must be >= 1
    
    response = client.post(
        "/api/events",
        json=invalid_data,
        headers=admin_headers
    )
    
    assert response.status_code == 422

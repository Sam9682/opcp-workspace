"""Tests for event registration endpoints
Feature: OPCP-website
Validates Requirements 6.3
"""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models import User, Event, EventRegistration, EventStatus, UserRole
from app.auth.password import hash_password


@pytest.fixture
def test_member(client: TestClient, db_session: Session) -> User:
    """Create a test member user"""
    user = User(
        email="member@test.com",
        password_hash=hash_password("Test1234"),
        first_name="Test",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_admin(client: TestClient, db_session: Session) -> User:
    """Create a test admin user"""
    user = User(
        email="admin@test.com",
        password_hash=hash_password("Admin1234"),
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
def test_event(client: TestClient, db_session: Session, test_admin: User) -> Event:
    """Create a test event"""
    event = Event(
        title="Test Event",
        description="Test event description",
        start_date=datetime.now(timezone.utc) + timedelta(days=7),
        end_date=datetime.now(timezone.utc) + timedelta(days=7, hours=2),
        location="Test Location",
        max_participants=10,
        created_by=test_admin.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


@pytest.fixture
def test_event_no_limit(client: TestClient, db_session: Session, test_admin: User) -> Event:
    """Create a test event without participant limit"""
    event = Event(
        title="Unlimited Event",
        description="Event with no participant limit",
        start_date=datetime.now(timezone.utc) + timedelta(days=14),
        end_date=datetime.now(timezone.utc) + timedelta(days=14, hours=2),
        location="Test Location",
        max_participants=None,
        created_by=test_admin.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


@pytest.fixture
def member_token(client: TestClient, test_member: User) -> str:
    """Get authentication token for test member"""
    response = client.post(
        "/api/auth/login",
        json={"email": "member@test.com", "password": "Test1234"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def admin_token(client: TestClient, test_admin: User) -> str:
    """Get authentication token for test admin"""
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "Admin1234"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_register_for_event_success(client: TestClient, 
    db_session: Session,
    test_event: Event,
    test_member: User,
    member_token: str
):
    """Test successful event registration
    
    Validates Requirements 6.3:
    - Creates EventRegistration record
    - Updates participant count
    """
    # Register for event
    response = client.post(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Successfully registered for event"
    assert data["registration_id"] is not None
    assert data["participant_count"] == 1
    
    # Verify registration in database
    registration = db_session.query(EventRegistration).filter(
        EventRegistration.event_id == test_event.id,
        EventRegistration.user_id == test_member.id
    ).first()
    
    assert registration is not None
    assert registration.event_id == test_event.id
    assert registration.user_id == test_member.id
    assert registration.attended is None


def test_register_for_event_unauthenticated(client: TestClient, test_event: Event):
    """Test event registration without authentication
    
    Validates Requirements 6.3:
    - Requires authentication
    """
    response = client.post(f"/api/events/{test_event.id}/register")
    
    assert response.status_code == 403


def test_register_for_event_not_found(client: TestClient, member_token: str):
    """Test registration for non-existent event
    
    Validates Requirements 6.3:
    - Returns 404 for non-existent event
    """
    fake_event_id = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        f"/api/events/{fake_event_id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == "EVENT_NOT_FOUND"


def test_register_for_event_invalid_id(client: TestClient, member_token: str):
    """Test registration with invalid event ID format
    
    Validates Requirements 6.3:
    - Validates event ID format
    """
    response = client.post(
        "/api/events/invalid-id/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"]["code"] == "INVALID_EVENT_ID"


def test_register_for_event_already_registered(client: TestClient, 
    db_session: Session,
    test_event: Event,
    test_member: User,
    member_token: str
):
    """Test duplicate registration prevention
    
    Validates Requirements 6.3:
    - Prevents duplicate registrations
    """
    # First registration
    response = client.post(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 201
    
    # Attempt duplicate registration
    response = client.post(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"]["code"] == "ALREADY_REGISTERED"


def test_register_for_event_max_participants_limit(client: TestClient, 
    db_session: Session,
    test_event: Event,
    test_admin: User,
    member_token: str
):
    """Test max_participants limit enforcement
    
    Validates Requirements 6.3:
    - Checks max_participants limit
    - Prevents registration when event is full
    """
    # Set max_participants to 2
    test_event.max_participants = 2
    db_session.commit()
    
    # Create another member
    member2 = User(
        email="member2@test.com",
        password_hash=hash_password("Test1234"),
        first_name="Member",
        last_name="Two",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(member2)
    db_session.commit()
    
    # Register first member
    response = client.post(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 201
    
    # Register second member
    response2 = client.post(
        "/api/auth/login",
        json={"email": "member2@test.com", "password": "Test1234"}
    )
    member2_token = response2.json()["access_token"]
    
    response = client.post(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member2_token}"}
    )
    assert response.status_code == 201
    
    # Create third member and attempt registration (should fail)
    member3 = User(
        email="member3@test.com",
        password_hash=hash_password("Test1234"),
        first_name="Member",
        last_name="Three",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(member3)
    db_session.commit()
    
    response3 = client.post(
        "/api/auth/login",
        json={"email": "member3@test.com", "password": "Test1234"}
    )
    member3_token = response3.json()["access_token"]
    
    response = client.post(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member3_token}"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"]["code"] == "EVENT_FULL"
    assert data["detail"]["error"]["details"]["max_participants"] == 2


def test_register_for_event_no_limit(client: TestClient, 
    db_session: Session,
    test_event_no_limit: Event,
    member_token: str
):
    """Test registration for event without participant limit
    
    Validates Requirements 6.3:
    - Allows registration when max_participants is None
    """
    response = client.post(
        f"/api/events/{test_event_no_limit.id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["participant_count"] == 1


def test_register_for_cancelled_event(client: TestClient, 
    db_session: Session,
    test_event: Event,
    member_token: str
):
    """Test registration for cancelled event
    
    Validates Requirements 6.3:
    - Prevents registration for cancelled events
    """
    # Cancel the event
    test_event.status = EventStatus.CANCELLED
    db_session.commit()
    
    response = client.post(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    
    assert response.status_code == 409
    data = response.json()
    assert data["detail"]["error"]["code"] == "EVENT_CANCELLED"


def test_unregister_from_event_success(client: TestClient, 
    db_session: Session,
    test_event: Event,
    test_member: User,
    member_token: str
):
    """Test successful event unregistration
    
    Validates Requirements 6.3:
    - Removes EventRegistration record
    - Updates participant count
    """
    # First register
    response = client.post(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 201
    
    # Verify registration exists
    registration = db_session.query(EventRegistration).filter(
        EventRegistration.event_id == test_event.id,
        EventRegistration.user_id == test_member.id
    ).first()
    assert registration is not None
    
    # Unregister
    response = client.delete(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Successfully unregistered from event"
    assert data["participant_count"] == 0
    
    # Verify registration removed from database
    registration = db_session.query(EventRegistration).filter(
        EventRegistration.event_id == test_event.id,
        EventRegistration.user_id == test_member.id
    ).first()
    assert registration is None


def test_unregister_from_event_unauthenticated(client: TestClient, test_event: Event):
    """Test event unregistration without authentication
    
    Validates Requirements 6.3:
    - Requires authentication
    """
    response = client.delete(f"/api/events/{test_event.id}/register")
    
    assert response.status_code == 403


def test_unregister_from_event_not_found(client: TestClient, member_token: str):
    """Test unregistration from non-existent event
    
    Validates Requirements 6.3:
    - Returns 404 for non-existent event
    """
    fake_event_id = "00000000-0000-0000-0000-000000000000"
    response = client.delete(
        f"/api/events/{fake_event_id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == "EVENT_NOT_FOUND"


def test_unregister_from_event_not_registered(client: TestClient, 
    test_event: Event,
    member_token: str
):
    """Test unregistration when not registered
    
    Validates Requirements 6.3:
    - Returns 404 when user is not registered
    """
    response = client.delete(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == "NOT_REGISTERED"


def test_unregister_from_event_invalid_id(client: TestClient, member_token: str):
    """Test unregistration with invalid event ID format
    
    Validates Requirements 6.3:
    - Validates event ID format
    """
    response = client.delete(
        "/api/events/invalid-id/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"]["code"] == "INVALID_EVENT_ID"


def test_participant_count_updates(client: TestClient, 
    db_session: Session,
    test_event: Event,
    test_admin: User,
    member_token: str
):
    """Test participant count updates correctly
    
    Validates Requirements 6.3:
    - Participant count increases on registration
    - Participant count decreases on unregistration
    """
    # Create additional members
    member2 = User(
        email="member2@test.com",
        password_hash=hash_password("Test1234"),
        first_name="Member",
        last_name="Two",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    member3 = User(
        email="member3@test.com",
        password_hash=hash_password("Test1234"),
        first_name="Member",
        last_name="Three",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add_all([member2, member3])
    db_session.commit()
    
    # Get tokens
    response2 = client.post(
        "/api/auth/login",
        json={"email": "member2@test.com", "password": "Test1234"}
    )
    member2_token = response2.json()["access_token"]
    
    response3 = client.post(
        "/api/auth/login",
        json={"email": "member3@test.com", "password": "Test1234"}
    )
    member3_token = response3.json()["access_token"]
    
    # Register member 1
    response = client.post(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 201
    assert response.json()["participant_count"] == 1
    
    # Register member 2
    response = client.post(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member2_token}"}
    )
    assert response.status_code == 201
    assert response.json()["participant_count"] == 2
    
    # Register member 3
    response = client.post(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member3_token}"}
    )
    assert response.status_code == 201
    assert response.json()["participant_count"] == 3
    
    # Unregister member 2
    response = client.delete(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member2_token}"}
    )
    assert response.status_code == 200
    assert response.json()["participant_count"] == 2
    
    # Unregister member 1
    response = client.delete(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    assert response.json()["participant_count"] == 1
    
    # Unregister member 3
    response = client.delete(
        f"/api/events/{test_event.id}/register",
        headers={"Authorization": f"Bearer {member3_token}"}
    )
    assert response.status_code == 200
    assert response.json()["participant_count"] == 0

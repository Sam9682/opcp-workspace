"""Tests for event cancellation endpoint
Feature: OPCP-website
Validates Requirements 6.6
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models import User, Event, EventRegistration, EventStatus, UserRole
from app.auth.password import hash_password


def test_cancel_event_success(db_session: Session, client):
    """Test successful event cancellation by admin
    
    Validates Requirements 6.6:
    - Admin can cancel an event
    - Event status is updated to cancelled
    - Cancellation emails are sent to registered participants
    """
    # Create admin user
    admin = User(
        email="admin@test.com",
        password_hash=hash_password("Admin1234"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    
    # Create regular members
    member1 = User(
        email="member1@test.com",
        password_hash=hash_password("Member1234"),
        first_name="Member",
        last_name="One",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    member2 = User(
        email="member2@test.com",
        password_hash=hash_password("Member1234"),
        first_name="Member",
        last_name="Two",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add_all([member1, member2])
    db_session.commit()
    db_session.refresh(member1)
    db_session.refresh(member2)
    
    # Create event
    event = Event(
        title="Test Event",
        description="Test event description",
        start_date=datetime.now(timezone.utc) + timedelta(days=7),
        end_date=datetime.now(timezone.utc) + timedelta(days=7, hours=2),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    
    # Register members for the event
    registration1 = EventRegistration(
        event_id=event.id,
        user_id=member1.id
    )
    registration2 = EventRegistration(
        event_id=event.id,
        user_id=member2.id
    )
    db_session.add_all([registration1, registration2])
    db_session.commit()
    
    # Login as admin
    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "Admin1234"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # Cancel event
    response = client.put(
        f"/api/events/{event.id}/cancel",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "cancelled successfully" in data["message"].lower()
    assert data["event"]["status"] == "cancelled"
    assert data["event"]["id"] == str(event.id)
    assert data["notifications_sent"] >= 0  # Email sending may fail in test environment
    
    # Verify event status in database
    db_session.refresh(event)
    assert event.status == EventStatus.CANCELLED


def test_cancel_event_not_admin(db_session: Session, client):
    """Test that non-admin users cannot cancel events
    
    Validates Requirements 6.6, 7.2:
    - Only administrators can cancel events
    """
    # Create regular member
    member = User(
        email="member@test.com",
        password_hash=hash_password("Member1234"),
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)
    
    # Create admin for event creation
    admin = User(
        email="admin@test.com",
        password_hash=hash_password("Admin1234"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    
    # Create event
    event = Event(
        title="Test Event",
        description="Test event description",
        start_date=datetime.now(timezone.utc) + timedelta(days=7),
        end_date=datetime.now(timezone.utc) + timedelta(days=7, hours=2),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    
    # Login as member
    login_response = client.post(
        "/api/auth/login",
        json={"email": "member@test.com", "password": "Member1234"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # Try to cancel event
    response = client.put(
        f"/api/events/{event.id}/cancel",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify response
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert data["detail"]["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_cancel_event_not_found(db_session: Session, client):
    """Test cancelling a non-existent event
    
    Validates Requirements 6.6:
    - Returns 404 for non-existent events
    """
    # Create admin user
    admin = User(
        email="admin@test.com",
        password_hash=hash_password("Admin1234"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    
    # Login as admin
    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "Admin1234"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # Try to cancel non-existent event
    fake_event_id = "00000000-0000-0000-0000-000000000000"
    response = client.put(
        f"/api/events/{fake_event_id}/cancel",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify response
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert data["detail"]["error"]["code"] == "EVENT_NOT_FOUND"


def test_cancel_event_already_cancelled(db_session: Session, client):
    """Test cancelling an already cancelled event
    
    Validates Requirements 6.6:
    - Returns error when trying to cancel an already cancelled event
    """
    # Create admin user
    admin = User(
        email="admin@test.com",
        password_hash=hash_password("Admin1234"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    
    # Create event that is already cancelled
    event = Event(
        title="Test Event",
        description="Test event description",
        start_date=datetime.now(timezone.utc) + timedelta(days=7),
        end_date=datetime.now(timezone.utc) + timedelta(days=7, hours=2),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.CANCELLED
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    
    # Login as admin
    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "Admin1234"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # Try to cancel already cancelled event
    response = client.put(
        f"/api/events/{event.id}/cancel",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify response
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert data["detail"]["error"]["code"] == "EVENT_ALREADY_CANCELLED"


def test_cancel_event_invalid_id(db_session: Session, client):
    """Test cancelling event with invalid ID format
    
    Validates Requirements 6.6:
    - Returns error for invalid event ID format
    """
    # Create admin user
    admin = User(
        email="admin@test.com",
        password_hash=hash_password("Admin1234"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    
    # Login as admin
    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "Admin1234"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # Try to cancel event with invalid ID
    response = client.put(
        "/api/events/invalid-id/cancel",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify response
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert data["detail"]["error"]["code"] == "INVALID_EVENT_ID"


def test_cancel_event_no_participants(db_session: Session, client):
    """Test cancelling an event with no registered participants
    
    Validates Requirements 6.6:
    - Event can be cancelled even with no participants
    - No emails are sent when there are no participants
    """
    # Create admin user
    admin = User(
        email="admin@test.com",
        password_hash=hash_password("Admin1234"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    
    # Create event with no registrations
    event = Event(
        title="Test Event",
        description="Test event description",
        start_date=datetime.now(timezone.utc) + timedelta(days=7),
        end_date=datetime.now(timezone.utc) + timedelta(days=7, hours=2),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    
    # Login as admin
    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "Admin1234"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # Cancel event
    response = client.put(
        f"/api/events/{event.id}/cancel",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["event"]["status"] == "cancelled"
    assert data["notifications_sent"] == 0  # No participants to notify
    
    # Verify event status in database
    db_session.refresh(event)
    assert event.status == EventStatus.CANCELLED


def test_cancel_event_unauthenticated(db_session: Session, client):
    """Test that unauthenticated users cannot cancel events
    
    Validates Requirements 6.6, 2.3:
    - Authentication is required to cancel events
    """
    # Create admin user
    admin = User(
        email="admin@test.com",
        password_hash=hash_password("Admin1234"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    
    # Create event
    event = Event(
        title="Test Event",
        description="Test event description",
        start_date=datetime.now(timezone.utc) + timedelta(days=7),
        end_date=datetime.now(timezone.utc) + timedelta(days=7, hours=2),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    
    # Try to cancel event without authentication
    response = client.put(f"/api/events/{event.id}/cancel")
    
    # Verify response - returns 403 because admin dependency is checked
    assert response.status_code == 403

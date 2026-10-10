"""Tests for event reminder service
Feature: OPCP-website
Validates Requirements 6.4
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models import User, Event, EventRegistration, EventStatus, UserRole
from app.services.event_reminder_service import event_reminder_service


def test_get_upcoming_events_7_days_before(db_session: Session):
    """Test getting events that start in 7 days
    
    Validates Requirements 6.4:
    - Identifies events starting in 7 days
    """
    # Create test user
    admin = User(
        email="admin@test.com",
        password_hash="hashed",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create events at different times
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Event in 7 days (should be included)
    event_7_days = Event(
        title="Event in 7 days",
        description="Test event",
        start_date=(now + timedelta(days=7)).replace(tzinfo=None),
        end_date=(now + timedelta(days=7, hours=2)).replace(tzinfo=None),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    
    # Event in 6 days (should not be included)
    event_6_days = Event(
        title="Event in 6 days",
        description="Test event",
        start_date=(now + timedelta(days=6)).replace(tzinfo=None),
        end_date=(now + timedelta(days=6, hours=2)).replace(tzinfo=None),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    
    # Event in 8 days (should not be included)
    event_8_days = Event(
        title="Event in 8 days",
        description="Test event",
        start_date=(now + timedelta(days=8)).replace(tzinfo=None),
        end_date=(now + timedelta(days=8, hours=2)).replace(tzinfo=None),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    
    # Cancelled event in 7 days (should not be included)
    event_cancelled = Event(
        title="Cancelled event in 7 days",
        description="Test event",
        start_date=(now + timedelta(days=7)).replace(tzinfo=None),
        end_date=(now + timedelta(days=7, hours=2)).replace(tzinfo=None),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.CANCELLED
    )
    
    db_session.add_all([event_7_days, event_6_days, event_8_days, event_cancelled])
    db_session.commit()
    
    # Get upcoming events
    upcoming_events = event_reminder_service.get_upcoming_events(db_session)
    
    # Should only return the event in 7 days
    assert len(upcoming_events) == 1
    assert upcoming_events[0].title == "Event in 7 days"
    assert upcoming_events[0].status == EventStatus.SCHEDULED


def test_get_event_participants(db_session: Session):
    """Test getting registered participants for an event
    
    Validates Requirements 6.4:
    - Only sends to registered participants
    """
    # Create test users
    admin = User(
        email="admin@test.com",
        password_hash="hashed",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    
    member1 = User(
        email="member1@test.com",
        password_hash="hashed",
        first_name="Member",
        last_name="One",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    
    member2 = User(
        email="member2@test.com",
        password_hash="hashed",
        first_name="Member",
        last_name="Two",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    
    # Unverified member (should not be included)
    member3 = User(
        email="member3@test.com",
        password_hash="hashed",
        first_name="Member",
        last_name="Three",
        role=UserRole.MEMBER,
        is_email_verified=False
    )
    
    db_session.add_all([admin, member1, member2, member3])
    db_session.commit()
    
    # Create event
    now = datetime.now(timezone.utc)
    event = Event(
        title="Test Event",
        description="Test event",
        start_date=(now + timedelta(days=7)).replace(tzinfo=None),
        end_date=(now + timedelta(days=7, hours=2)).replace(tzinfo=None),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    
    # Register members
    registration1 = EventRegistration(event_id=event.id, user_id=member1.id)
    registration2 = EventRegistration(event_id=event.id, user_id=member2.id)
    registration3 = EventRegistration(event_id=event.id, user_id=member3.id)
    
    db_session.add_all([registration1, registration2, registration3])
    db_session.commit()
    
    # Get participants
    participants = event_reminder_service.get_event_participants(db_session, event.id)
    
    # Should only return verified members
    assert len(participants) == 2
    participant_emails = [p.email for p in participants]
    assert "member1@test.com" in participant_emails
    assert "member2@test.com" in participant_emails
    assert "member3@test.com" not in participant_emails  # Unverified


def test_send_event_reminder(db_session: Session, mocker):
    """Test sending event reminder email
    
    Validates Requirements 6.4:
    - Sends reminder emails with event details
    """
    # Mock email service
    mock_send_email = mocker.patch('app.services.event_reminder_service.email_service.send_email')
    mock_send_email.return_value = True
    
    # Create test user
    member = User(
        email="member@test.com",
        password_hash="hashed",
        first_name="John",
        last_name="Doe",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(member)
    db_session.commit()
    
    # Create event
    now = datetime.now(timezone.utc)
    event = Event(
        title="Test Event",
        description="This is a test event",
        start_date=(now + timedelta(days=7)).replace(tzinfo=None),
        end_date=(now + timedelta(days=7, hours=2)).replace(tzinfo=None),
        location="Test Location",
        created_by=member.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    
    # Send reminder
    result = event_reminder_service.send_event_reminder(member, event)
    
    # Verify email was sent
    assert result is True
    mock_send_email.assert_called_once()
    
    # Verify email content
    call_args = mock_send_email.call_args
    assert call_args[1]['to_email'] == "member@test.com"
    assert "Test Event" in call_args[1]['subject']
    assert "John Doe" in call_args[1]['body_text']
    assert "Test Event" in call_args[1]['body_text']
    assert "Test Location" in call_args[1]['body_text']
    assert "This is a test event" in call_args[1]['body_text']
    assert "7 jours" in call_args[1]['body_text'] or "7 days" in call_args[1]['body_text']


def test_process_event_reminders(db_session: Session, mocker):
    """Test processing all event reminders
    
    Validates Requirements 6.4:
    - Processes all upcoming events
    - Sends reminders to all registered participants
    """
    # Mock email service
    mock_send_email = mocker.patch('app.services.event_reminder_service.email_service.send_email')
    mock_send_email.return_value = True
    
    # Create test users
    admin = User(
        email="admin@test.com",
        password_hash="hashed",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    
    member1 = User(
        email="member1@test.com",
        password_hash="hashed",
        first_name="Member",
        last_name="One",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    
    member2 = User(
        email="member2@test.com",
        password_hash="hashed",
        first_name="Member",
        last_name="Two",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    
    db_session.add_all([admin, member1, member2])
    db_session.commit()
    
    # Create events in 7 days
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    event1 = Event(
        title="Event 1",
        description="Test event 1",
        start_date=(now + timedelta(days=7)).replace(tzinfo=None),
        end_date=(now + timedelta(days=7, hours=2)).replace(tzinfo=None),
        location="Location 1",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    
    event2 = Event(
        title="Event 2",
        description="Test event 2",
        start_date=(now + timedelta(days=7, hours=3)).replace(tzinfo=None),
        end_date=(now + timedelta(days=7, hours=5)).replace(tzinfo=None),
        location="Location 2",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    
    db_session.add_all([event1, event2])
    db_session.commit()
    
    # Register members for events
    # Event 1: member1 and member2
    # Event 2: member1 only
    registration1 = EventRegistration(event_id=event1.id, user_id=member1.id)
    registration2 = EventRegistration(event_id=event1.id, user_id=member2.id)
    registration3 = EventRegistration(event_id=event2.id, user_id=member1.id)
    
    db_session.add_all([registration1, registration2, registration3])
    db_session.commit()
    
    # Process reminders
    result = event_reminder_service.process_event_reminders(db_session)
    
    # Verify results
    assert result['events'] == 2  # 2 events in 7 days
    assert result['participants'] == 3  # 2 for event1 + 1 for event2
    assert result['sent'] == 3  # All emails sent successfully
    assert result['failed'] == 0
    
    # Verify email was called 3 times
    assert mock_send_email.call_count == 3


def test_process_event_reminders_no_events(db_session: Session, mocker):
    """Test processing when no events are upcoming
    
    Validates Requirements 6.4:
    - Handles case with no upcoming events
    """
    # Mock email service
    mock_send_email = mocker.patch('app.services.event_reminder_service.email_service.send_email')
    
    # Process reminders (no events in database)
    result = event_reminder_service.process_event_reminders(db_session)
    
    # Verify results
    assert result['events'] == 0
    assert result['participants'] == 0
    assert result['sent'] == 0
    assert result['failed'] == 0
    
    # Verify email was never called
    mock_send_email.assert_not_called()


def test_process_event_reminders_no_participants(db_session: Session, mocker):
    """Test processing when events have no registered participants
    
    Validates Requirements 6.4:
    - Handles events with no registrations
    """
    # Mock email service
    mock_send_email = mocker.patch('app.services.event_reminder_service.email_service.send_email')
    
    # Create test user
    admin = User(
        email="admin@test.com",
        password_hash="hashed",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create event in 7 days with no registrations
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    event = Event(
        title="Event with no participants",
        description="Test event",
        start_date=(now + timedelta(days=7)).replace(tzinfo=None),
        end_date=(now + timedelta(days=7, hours=2)).replace(tzinfo=None),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    
    # Process reminders
    result = event_reminder_service.process_event_reminders(db_session)
    
    # Verify results
    assert result['events'] == 1  # 1 event found
    assert result['participants'] == 0  # No participants
    assert result['sent'] == 0
    assert result['failed'] == 0
    
    # Verify email was never called
    mock_send_email.assert_not_called()


def test_process_event_reminders_email_failure(db_session: Session, mocker):
    """Test processing when email sending fails
    
    Validates Requirements 6.4:
    - Handles email sending failures gracefully
    """
    # Mock email service to fail
    mock_send_email = mocker.patch('app.services.event_reminder_service.email_service.send_email')
    mock_send_email.return_value = False
    
    # Create test users
    admin = User(
        email="admin@test.com",
        password_hash="hashed",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    
    member = User(
        email="member@test.com",
        password_hash="hashed",
        first_name="Member",
        last_name="One",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    
    db_session.add_all([admin, member])
    db_session.commit()
    
    # Create event in 7 days
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    event = Event(
        title="Test Event",
        description="Test event",
        start_date=(now + timedelta(days=7)).replace(tzinfo=None),
        end_date=(now + timedelta(days=7, hours=2)).replace(tzinfo=None),
        location="Test Location",
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    
    # Register member
    registration = EventRegistration(event_id=event.id, user_id=member.id)
    db_session.add(registration)
    db_session.commit()
    
    # Process reminders
    result = event_reminder_service.process_event_reminders(db_session)
    
    # Verify results
    assert result['events'] == 1
    assert result['participants'] == 1
    assert result['sent'] == 0  # Email failed
    assert result['failed'] == 1
    
    # Verify email was called once
    mock_send_email.assert_called_once()

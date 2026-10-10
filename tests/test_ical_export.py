"""Tests for iCal export endpoint
Feature: OPCP-website
Validates Requirements 6.7
"""
import pytest
from datetime import datetime, timedelta, timezone
from icalendar import Calendar
from app.models import User, Event, EventStatus, UserRole


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        email="testuser@example.com",
        password_hash="hashed_password",
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
def auth_headers(test_user):
    """Get authentication headers for test user"""
    from app.auth.token import create_access_token
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_events(db_session, test_user):
    """Create test events"""
    now = datetime.now(timezone.utc)
    
    events = [
        Event(
            title="Test Event 1",
            description="First test event description",
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=1, hours=2),
            location="Test Location 1",
            max_participants=10,
            created_by=test_user.id,
            status=EventStatus.SCHEDULED
        ),
        Event(
            title="Test Event 2",
            description="Second test event description",
            start_date=now + timedelta(days=7),
            end_date=now + timedelta(days=7, hours=3),
            location="Test Location 2",
            max_participants=None,
            created_by=test_user.id,
            status=EventStatus.SCHEDULED
        ),
        Event(
            title="Test Event 3 - No Description",
            description=None,
            start_date=now + timedelta(days=14),
            end_date=now + timedelta(days=14, hours=1),
            location=None,
            max_participants=5,
            created_by=test_user.id,
            status=EventStatus.SCHEDULED
        ),
        # Cancelled event - should not be included
        Event(
            title="Cancelled Event",
            description="This event is cancelled",
            start_date=now + timedelta(days=3),
            end_date=now + timedelta(days=3, hours=2),
            location="Cancelled Location",
            max_participants=10,
            created_by=test_user.id,
            status=EventStatus.CANCELLED
        ),
        # Past event - should not be included
        Event(
            title="Past Event",
            description="This event is in the past",
            start_date=now - timedelta(days=7),
            end_date=now - timedelta(days=7, hours=2),
            location="Past Location",
            max_participants=10,
            created_by=test_user.id,
            status=EventStatus.COMPLETED
        )
    ]
    
    for event in events:
        db_session.add(event)
    
    db_session.commit()
    
    for event in events:
        db_session.refresh(event)
    
    return events


def test_ical_export_requires_authentication(client):
    """Test that iCal export requires authentication"""
    response = client.get("/api/events/export/ical")
    # Should return 401 or 403 when not authenticated
    assert response.status_code in [401, 403]


def test_ical_export_returns_valid_ical(client, db_session, test_events, auth_headers):
    """Test that iCal export returns valid iCal format
    
    Validates Requirements 6.7:
    - Generates valid iCal format file
    - File is parseable by standard calendar applications
    """
    response = client.get("/api/events/export/ical", headers=auth_headers)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/calendar; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    assert "OPCP_events.ics" in response.headers["content-disposition"]
    
    # Parse the iCal content to verify it's valid
    cal = Calendar.from_ical(response.content)
    
    # Verify calendar properties
    assert cal.get('prodid') == '-//OPCP PSMC//Events Calendar//FR'
    assert cal.get('version') == '2.0'
    assert cal.get('calscale') == 'GREGORIAN'
    assert cal.get('method') == 'PUBLISH'


def test_ical_export_includes_all_event_details(client, db_session, test_events, auth_headers):
    """Test that iCal export includes all event details
    
    Validates Requirements 6.7:
    - Includes all event details (title, description, dates, location)
    """
    response = client.get("/api/events/export/ical", headers=auth_headers)
    
    assert response.status_code == 200
    
    # Parse the iCal content
    cal = Calendar.from_ical(response.content)
    
    # Get all events from the calendar
    ical_events = [component for component in cal.walk() if component.name == "VEVENT"]
    
    # Should only include 3 scheduled upcoming events (not cancelled or past)
    assert len(ical_events) == 3
    
    # Verify first event details
    event1 = ical_events[0]
    assert event1.get('summary') == "Test Event 1"
    assert event1.get('description') == "First test event description"
    assert event1.get('location') == "Test Location 1"
    assert event1.get('status') == 'CONFIRMED'
    assert event1.get('uid') is not None
    assert '@OPCP.org' in str(event1.get('uid'))
    
    # Verify event with no description
    event3 = ical_events[2]
    assert event3.get('summary') == "Test Event 3 - No Description"
    # Description should be None or empty
    desc = event3.get('description')
    assert desc is None or desc == ''


def test_ical_export_only_includes_upcoming_scheduled_events(client, db_session, test_events, auth_headers):
    """Test that iCal export only includes upcoming scheduled events
    
    Validates Requirements 6.7:
    - Only exports upcoming events (not past or cancelled)
    """
    response = client.get("/api/events/export/ical", headers=auth_headers)
    
    assert response.status_code == 200
    
    # Parse the iCal content
    cal = Calendar.from_ical(response.content)
    
    # Get all events from the calendar
    ical_events = [component for component in cal.walk() if component.name == "VEVENT"]
    
    # Should only include 3 scheduled upcoming events
    assert len(ical_events) == 3
    
    # Verify that cancelled and past events are not included
    event_titles = [event.get('summary') for event in ical_events]
    assert "Cancelled Event" not in event_titles
    assert "Past Event" not in event_titles
    assert "Test Event 1" in event_titles
    assert "Test Event 2" in event_titles
    assert "Test Event 3 - No Description" in event_titles


def test_ical_export_with_no_events(client, db_session, test_user, auth_headers):
    """Test iCal export when there are no upcoming events"""
    response = client.get("/api/events/export/ical", headers=auth_headers)
    
    assert response.status_code == 200
    
    # Parse the iCal content
    cal = Calendar.from_ical(response.content)
    
    # Get all events from the calendar
    ical_events = [component for component in cal.walk() if component.name == "VEVENT"]
    
    # Should have no events
    assert len(ical_events) == 0


def test_ical_export_event_dates_are_correct(client, db_session, test_events, auth_headers):
    """Test that event dates in iCal export are correct"""
    response = client.get("/api/events/export/ical", headers=auth_headers)
    
    assert response.status_code == 200
    
    # Parse the iCal content
    cal = Calendar.from_ical(response.content)
    
    # Get all events from the calendar
    ical_events = [component for component in cal.walk() if component.name == "VEVENT"]
    
    # Verify first event dates
    event1 = ical_events[0]
    dtstart = event1.get('dtstart').dt
    dtend = event1.get('dtend').dt
    
    # Verify dates are datetime objects
    assert isinstance(dtstart, datetime)
    assert isinstance(dtend, datetime)
    
    # Verify end date is after start date
    assert dtend > dtstart


def test_ical_export_includes_required_ical_fields(client, db_session, test_events, auth_headers):
    """Test that iCal export includes all required iCal fields
    
    Validates Requirements 6.7:
    - Generates valid iCal format with required fields
    """
    response = client.get("/api/events/export/ical", headers=auth_headers)
    
    assert response.status_code == 200
    
    # Parse the iCal content
    cal = Calendar.from_ical(response.content)
    
    # Get all events from the calendar
    ical_events = [component for component in cal.walk() if component.name == "VEVENT"]
    
    # Verify each event has required fields
    for ical_event in ical_events:
        # Required fields according to RFC 5545
        assert ical_event.get('uid') is not None
        assert ical_event.get('dtstamp') is not None
        assert ical_event.get('dtstart') is not None
        assert ical_event.get('dtend') is not None
        assert ical_event.get('summary') is not None
        
        # Additional fields we include
        assert ical_event.get('status') is not None
        assert ical_event.get('created') is not None
        assert ical_event.get('last-modified') is not None

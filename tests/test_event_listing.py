"""Tests for event listing endpoint
Feature: OPCP-website
Validates Requirements 6.1, 6.5
"""
import pytest
from datetime import datetime, timedelta, timezone
from app.models import User, UserRole, Event, EventStatus, EventRegistration


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
def member_headers(member_user):
    """Create authentication headers with member JWT token"""
    from app.auth.token import create_access_token
    
    token = create_access_token({"sub": str(member_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def upcoming_events(db_session, admin_user):
    """Create upcoming events for tests"""
    now = datetime.now(timezone.utc)
    
    events = [
        Event(
            title="Event 1 - Tomorrow",
            description="First upcoming event",
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=1, hours=2),
            location="Location 1",
            max_participants=50,
            created_by=admin_user.id,
            status=EventStatus.SCHEDULED
        ),
        Event(
            title="Event 2 - Next Week",
            description="Second upcoming event",
            start_date=now + timedelta(days=7),
            end_date=now + timedelta(days=7, hours=3),
            location="Location 2",
            max_participants=30,
            created_by=admin_user.id,
            status=EventStatus.SCHEDULED
        ),
        Event(
            title="Event 3 - Next Month",
            description="Third upcoming event",
            start_date=now + timedelta(days=30),
            end_date=now + timedelta(days=30, hours=1),
            location="Location 3",
            max_participants=None,
            created_by=admin_user.id,
            status=EventStatus.SCHEDULED
        )
    ]
    
    db_session.add_all(events)
    db_session.commit()
    
    for event in events:
        db_session.refresh(event)
    
    return events


@pytest.fixture
def past_events(db_session, admin_user):
    """Create past events for tests"""
    now = datetime.now(timezone.utc)
    
    events = [
        Event(
            title="Past Event 1",
            description="Event that already happened",
            start_date=now - timedelta(days=7),
            end_date=now - timedelta(days=7, hours=-2),
            location="Past Location",
            created_by=admin_user.id,
            status=EventStatus.COMPLETED
        ),
        Event(
            title="Past Event 2",
            description="Another past event",
            start_date=now - timedelta(days=1),
            end_date=now - timedelta(hours=22),
            location="Past Location 2",
            created_by=admin_user.id,
            status=EventStatus.COMPLETED
        )
    ]
    
    db_session.add_all(events)
    db_session.commit()
    
    for event in events:
        db_session.refresh(event)
    
    return events


@pytest.fixture
def cancelled_event(db_session, admin_user):
    """Create a cancelled event for tests"""
    now = datetime.now(timezone.utc)
    
    event = Event(
        title="Cancelled Event",
        description="This event was cancelled",
        start_date=now + timedelta(days=5),
        end_date=now + timedelta(days=5, hours=2),
        location="Cancelled Location",
        created_by=admin_user.id,
        status=EventStatus.CANCELLED
    )
    
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    
    return event


def test_list_events_success(client, member_headers, upcoming_events):
    """Test successful listing of upcoming events
    
    Validates Requirements 6.1:
    - Displays all upcoming events
    """
    response = client.get(
        "/api/events",
        headers=member_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert data["total"] == 3
    assert len(data["events"]) == 3
    assert data["view_format"] == "list"  # Default view
    
    # Verify events are returned
    event_titles = [event["title"] for event in data["events"]]
    assert "Event 1 - Tomorrow" in event_titles
    assert "Event 2 - Next Week" in event_titles
    assert "Event 3 - Next Month" in event_titles


def test_list_events_filters_past_events(client, member_headers, upcoming_events, past_events):
    """Test that past events are not included in listing
    
    Validates Requirements 6.1:
    - Only displays events with start_date >= current date
    """
    response = client.get(
        "/api/events",
        headers=member_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should only return upcoming events, not past events
    assert data["total"] == 3
    event_titles = [event["title"] for event in data["events"]]
    assert "Past Event 1" not in event_titles
    assert "Past Event 2" not in event_titles


def test_list_events_filters_cancelled_events(client, member_headers, upcoming_events, cancelled_event):
    """Test that cancelled events are not included in listing
    
    Validates Requirements 6.1:
    - Only displays scheduled events
    """
    response = client.get(
        "/api/events",
        headers=member_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should only return scheduled events, not cancelled
    assert data["total"] == 3
    event_titles = [event["title"] for event in data["events"]]
    assert "Cancelled Event" not in event_titles


def test_list_events_chronological_order(client, member_headers, upcoming_events):
    """Test that events are returned in chronological order
    
    Validates Requirements 6.1:
    - Events are ordered by start_date ascending
    """
    response = client.get(
        "/api/events",
        headers=member_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify chronological order
    assert data["events"][0]["title"] == "Event 1 - Tomorrow"
    assert data["events"][1]["title"] == "Event 2 - Next Week"
    assert data["events"][2]["title"] == "Event 3 - Next Month"
    
    # Verify dates are in ascending order
    dates = [event["start_date"] for event in data["events"]]
    assert dates == sorted(dates)


def test_list_events_includes_participant_count(client, member_headers, upcoming_events, member_user, db_session):
    """Test that events include participant count
    
    Validates Requirements 6.1:
    - Each event includes the number of registered participants
    """
    # Register member for first event
    registration = EventRegistration(
        event_id=upcoming_events[0].id,
        user_id=member_user.id
    )
    db_session.add(registration)
    db_session.commit()
    
    response = client.get(
        "/api/events",
        headers=member_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # First event should have 1 participant
    assert data["events"][0]["participant_count"] == 1
    # Other events should have 0 participants
    assert data["events"][1]["participant_count"] == 0
    assert data["events"][2]["participant_count"] == 0


def test_list_events_list_view(client, member_headers, upcoming_events):
    """Test list view format
    
    Validates Requirements 6.5:
    - Supports list view format
    """
    response = client.get(
        "/api/events?view=list",
        headers=member_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert data["view_format"] == "list"
    assert data["total"] == 3


def test_list_events_calendar_view(client, member_headers, upcoming_events):
    """Test calendar view format
    
    Validates Requirements 6.5:
    - Supports calendar view format
    """
    response = client.get(
        "/api/events?view=calendar",
        headers=member_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert data["view_format"] == "calendar"
    assert data["total"] == 3


def test_list_events_view_consistency(client, member_headers, upcoming_events):
    """Test that both views return the same events
    
    Validates Requirements 6.5:
    - Both calendar and list views display the same events
    """
    # Get list view
    list_response = client.get(
        "/api/events?view=list",
        headers=member_headers
    )
    
    # Get calendar view
    calendar_response = client.get(
        "/api/events?view=calendar",
        headers=member_headers
    )
    
    assert list_response.status_code == 200
    assert calendar_response.status_code == 200
    
    list_data = list_response.json()
    calendar_data = calendar_response.json()
    
    # Both views should return the same number of events
    assert list_data["total"] == calendar_data["total"]
    assert len(list_data["events"]) == len(calendar_data["events"])
    
    # Both views should return the same event IDs
    list_ids = {event["id"] for event in list_data["events"]}
    calendar_ids = {event["id"] for event in calendar_data["events"]}
    assert list_ids == calendar_ids
    
    # Both views should return events in the same order
    list_titles = [event["title"] for event in list_data["events"]]
    calendar_titles = [event["title"] for event in calendar_data["events"]]
    assert list_titles == calendar_titles


def test_list_events_invalid_view_parameter(client, member_headers, upcoming_events):
    """Test that invalid view parameter is rejected
    
    Validates Requirements 6.5:
    - Only accepts 'list' or 'calendar' as view parameter
    """
    response = client.get(
        "/api/events?view=invalid",
        headers=member_headers
    )
    
    # FastAPI query validation returns 422 for invalid enum values
    assert response.status_code == 422


def test_list_events_unauthenticated(client, upcoming_events):
    """Test that unauthenticated users cannot list events
    
    Validates Requirements 6.1:
    - Only authenticated members can access event listing
    """
    response = client.get("/api/events")
    
    assert response.status_code == 403  # FastAPI HTTPBearer returns 403 for missing auth


def test_list_events_empty_list(client, member_headers):
    """Test listing events when no upcoming events exist
    
    Validates Requirements 6.1:
    - Returns empty list when no upcoming events
    """
    response = client.get(
        "/api/events",
        headers=member_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert data["total"] == 0
    assert len(data["events"]) == 0


def test_list_events_includes_all_event_details(client, member_headers, upcoming_events):
    """Test that all event details are included in response
    
    Validates Requirements 6.1:
    - Each event includes all relevant details
    """
    response = client.get(
        "/api/events",
        headers=member_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check first event has all fields
    event = data["events"][0]
    assert "id" in event
    assert "title" in event
    assert "description" in event
    assert "start_date" in event
    assert "end_date" in event
    assert "location" in event
    assert "max_participants" in event
    assert "created_by" in event
    assert "status" in event
    assert "created_at" in event
    assert "updated_at" in event
    assert "participant_count" in event
    
    # Verify values
    assert event["title"] == "Event 1 - Tomorrow"
    assert event["description"] == "First upcoming event"
    assert event["location"] == "Location 1"
    assert event["max_participants"] == 50
    assert event["status"] == "scheduled"


def test_list_events_handles_null_optional_fields(client, member_headers, db_session, admin_user):
    """Test that events with null optional fields are handled correctly
    
    Validates Requirements 6.1:
    - Events with null description, location, or max_participants are displayed correctly
    """
    now = datetime.now(timezone.utc)
    
    # Create event with minimal fields
    minimal_event = Event(
        title="Minimal Event",
        description=None,
        start_date=now + timedelta(days=1),
        end_date=now + timedelta(days=1, hours=1),
        location=None,
        max_participants=None,
        created_by=admin_user.id,
        status=EventStatus.SCHEDULED
    )
    
    db_session.add(minimal_event)
    db_session.commit()
    
    response = client.get(
        "/api/events",
        headers=member_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Find the minimal event
    minimal_event_data = next(e for e in data["events"] if e["title"] == "Minimal Event")
    
    assert minimal_event_data["description"] is None
    assert minimal_event_data["location"] is None
    assert minimal_event_data["max_participants"] is None


def test_list_events_default_view_is_list(client, member_headers, upcoming_events):
    """Test that default view format is 'list'
    
    Validates Requirements 6.5:
    - Default view format is 'list' when not specified
    """
    response = client.get(
        "/api/events",
        headers=member_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["view_format"] == "list"

"""Tests for Event and EventRegistration models"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import IntegrityError
from app.models import Event, EventRegistration, EventStatus, User, UserRole


def test_create_event(db_session):
    """Test creating an event record"""
    # Create a user (admin) first
    admin = User(
        email="admin@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create an event
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    
    event = Event(
        title="Annual General Meeting",
        description="Annual meeting for all members",
        start_date=start_date,
        end_date=end_date,
        location="Main Office",
        max_participants=50,
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    
    # Verify event was created
    assert event.id is not None
    assert event.title == "Annual General Meeting"
    assert event.description == "Annual meeting for all members"
    # Compare timestamps - database may strip timezone info but values should match
    assert event.start_date.replace(tzinfo=None, microsecond=0) == start_date.replace(tzinfo=None, microsecond=0)
    assert event.end_date.replace(tzinfo=None, microsecond=0) == end_date.replace(tzinfo=None, microsecond=0)
    assert event.location == "Main Office"
    assert event.max_participants == 50
    assert event.created_by == admin.id
    assert event.status == EventStatus.SCHEDULED
    assert event.created_at is not None
    assert event.updated_at is not None
    assert isinstance(event.created_at, datetime)


def test_event_default_status(db_session):
    """Test that event status defaults to SCHEDULED"""
    admin = User(
        email="admin2@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    
    event = Event(
        title="Workshop",
        start_date=start_date,
        end_date=end_date,
        created_by=admin.id
    )
    db_session.add(event)
    db_session.commit()
    
    assert event.status == EventStatus.SCHEDULED


def test_event_status_enum(db_session):
    """Test EventStatus enum values"""
    admin = User(
        email="admin3@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    
    # Test all status values
    statuses = [
        EventStatus.SCHEDULED,
        EventStatus.CANCELLED,
        EventStatus.COMPLETED
    ]
    
    for status in statuses:
        event = Event(
            title=f"Event {status.value}",
            start_date=start_date,
            end_date=end_date,
            created_by=admin.id,
            status=status
        )
        db_session.add(event)
        db_session.commit()
        assert event.status == status


def test_event_optional_fields(db_session):
    """Test that description, location, and max_participants are optional"""
    admin = User(
        email="admin4@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    
    event = Event(
        title="Simple Event",
        start_date=start_date,
        end_date=end_date,
        created_by=admin.id
    )
    db_session.add(event)
    db_session.commit()
    
    assert event.description is None
    assert event.location is None
    assert event.max_participants is None


def test_event_creator_relationship(db_session):
    """Test relationship between Event and creator User"""
    admin = User(
        email="admin5@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    
    event = Event(
        title="Test Event",
        start_date=start_date,
        end_date=end_date,
        created_by=admin.id
    )
    db_session.add(event)
    db_session.commit()
    
    # Test relationship from event to creator
    assert event.creator == admin
    
    # Test relationship from user to events
    assert len(admin.events) == 1
    assert admin.events[0] == event


def test_event_start_date_index(db_session):
    """Test that index on start_date exists and works efficiently"""
    admin = User(
        email="admin6@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create multiple events with different start dates
    base_date = datetime.now(timezone.utc)
    for i in range(5):
        start_date = base_date + timedelta(days=i)
        end_date = start_date + timedelta(hours=2)
        event = Event(
            title=f"Event {i}",
            start_date=start_date,
            end_date=end_date,
            created_by=admin.id
        )
        db_session.add(event)
    db_session.commit()
    
    # Query by start_date (should use idx_events_start_date)
    future_events = db_session.query(Event).filter(
        Event.start_date >= base_date + timedelta(days=2)
    ).all()
    assert len(future_events) == 3


def test_create_event_registration(db_session):
    """Test creating an event registration"""
    # Create admin and member
    admin = User(
        email="admin7@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    member = User(
        email="member@example.com",
        password_hash="hashed_password",
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add_all([admin, member])
    db_session.commit()
    
    # Create event
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    event = Event(
        title="Test Event",
        start_date=start_date,
        end_date=end_date,
        created_by=admin.id
    )
    db_session.add(event)
    db_session.commit()
    
    # Create registration
    registration = EventRegistration(
        event_id=event.id,
        user_id=member.id
    )
    db_session.add(registration)
    db_session.commit()
    
    # Verify registration was created
    assert registration.id is not None
    assert registration.event_id == event.id
    assert registration.user_id == member.id
    assert registration.registered_at is not None
    assert isinstance(registration.registered_at, datetime)
    assert registration.attended is None


def test_event_registration_relationships(db_session):
    """Test relationships between EventRegistration, Event, and User"""
    # Create admin and member
    admin = User(
        email="admin8@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    member = User(
        email="member2@example.com",
        password_hash="hashed_password",
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add_all([admin, member])
    db_session.commit()
    
    # Create event
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    event = Event(
        title="Test Event",
        start_date=start_date,
        end_date=end_date,
        created_by=admin.id
    )
    db_session.add(event)
    db_session.commit()
    
    # Create registration
    registration = EventRegistration(
        event_id=event.id,
        user_id=member.id
    )
    db_session.add(registration)
    db_session.commit()
    
    # Test relationship from registration to event
    assert registration.event == event
    
    # Test relationship from registration to user
    assert registration.user == member
    
    # Test relationship from event to registrations
    assert len(event.registrations) == 1
    assert event.registrations[0] == registration
    
    # Test relationship from user to registrations
    assert len(member.event_registrations) == 1
    assert member.event_registrations[0] == registration


def test_unique_event_user_registration(db_session):
    """Test that a user cannot register twice for the same event"""
    # Create admin and member
    admin = User(
        email="admin9@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    member = User(
        email="member3@example.com",
        password_hash="hashed_password",
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add_all([admin, member])
    db_session.commit()
    
    # Create event
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    event = Event(
        title="Test Event",
        start_date=start_date,
        end_date=end_date,
        created_by=admin.id
    )
    db_session.add(event)
    db_session.commit()
    
    # Create first registration
    registration1 = EventRegistration(
        event_id=event.id,
        user_id=member.id
    )
    db_session.add(registration1)
    db_session.commit()
    
    # Try to create duplicate registration
    registration2 = EventRegistration(
        event_id=event.id,
        user_id=member.id
    )
    db_session.add(registration2)
    
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_event_registration_cascade_delete(db_session):
    """Test that deleting an event cascades to registrations"""
    # Create admin and member
    admin = User(
        email="admin10@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    member = User(
        email="member4@example.com",
        password_hash="hashed_password",
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add_all([admin, member])
    db_session.commit()
    
    # Create event
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    event = Event(
        title="Test Event",
        start_date=start_date,
        end_date=end_date,
        created_by=admin.id
    )
    db_session.add(event)
    db_session.commit()
    
    # Create registration
    registration = EventRegistration(
        event_id=event.id,
        user_id=member.id
    )
    db_session.add(registration)
    db_session.commit()
    
    registration_id = registration.id
    
    # Delete event
    db_session.delete(event)
    db_session.commit()
    
    # Verify registration was also deleted
    deleted_registration = db_session.query(EventRegistration).filter(
        EventRegistration.id == registration_id
    ).first()
    assert deleted_registration is None


def test_event_registration_attended_tracking(db_session):
    """Test tracking attendance status"""
    # Create admin and member
    admin = User(
        email="admin11@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    member = User(
        email="member5@example.com",
        password_hash="hashed_password",
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add_all([admin, member])
    db_session.commit()
    
    # Create event
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    event = Event(
        title="Test Event",
        start_date=start_date,
        end_date=end_date,
        created_by=admin.id
    )
    db_session.add(event)
    db_session.commit()
    
    # Create registration
    registration = EventRegistration(
        event_id=event.id,
        user_id=member.id
    )
    db_session.add(registration)
    db_session.commit()
    
    # Initially attended should be None
    assert registration.attended is None
    
    # Mark as attended
    registration.attended = True
    db_session.commit()
    assert registration.attended is True
    
    # Mark as not attended
    registration.attended = False
    db_session.commit()
    assert registration.attended is False


def test_event_registration_index(db_session):
    """Test that index on event_id exists"""
    # Create admin and members
    admin = User(
        email="admin12@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create event
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    event = Event(
        title="Test Event",
        start_date=start_date,
        end_date=end_date,
        created_by=admin.id
    )
    db_session.add(event)
    db_session.commit()
    
    # Create multiple registrations
    for i in range(5):
        member = User(
            email=f"member{i+10}@example.com",
            password_hash="hashed_password",
            first_name=f"Member{i}",
            last_name="User",
            role=UserRole.MEMBER,
            is_email_verified=True
        )
        db_session.add(member)
        db_session.commit()
        
        registration = EventRegistration(
            event_id=event.id,
            user_id=member.id
        )
        db_session.add(registration)
    db_session.commit()
    
    # Query by event_id (should use idx_registrations_event)
    registrations = db_session.query(EventRegistration).filter(
        EventRegistration.event_id == event.id
    ).all()
    assert len(registrations) == 5


def test_event_repr(db_session):
    """Test Event __repr__ method"""
    admin = User(
        email="admin13@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    
    event = Event(
        title="Test Event",
        start_date=start_date,
        end_date=end_date,
        created_by=admin.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    
    repr_str = repr(event)
    assert "Event" in repr_str
    assert str(event.id) in repr_str
    assert "Test Event" in repr_str
    assert "SCHEDULED" in repr_str


def test_event_registration_repr(db_session):
    """Test EventRegistration __repr__ method"""
    # Create admin and member
    admin = User(
        email="admin14@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    member = User(
        email="member6@example.com",
        password_hash="hashed_password",
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add_all([admin, member])
    db_session.commit()
    
    # Create event
    start_date = datetime.now(timezone.utc) + timedelta(days=7)
    end_date = start_date + timedelta(hours=2)
    event = Event(
        title="Test Event",
        start_date=start_date,
        end_date=end_date,
        created_by=admin.id
    )
    db_session.add(event)
    db_session.commit()
    
    # Create registration
    registration = EventRegistration(
        event_id=event.id,
        user_id=member.id
    )
    db_session.add(registration)
    db_session.commit()
    
    repr_str = repr(registration)
    assert "EventRegistration" in repr_str
    assert str(registration.id) in repr_str
    assert str(event.id) in repr_str
    assert str(member.id) in repr_str

"""Event models for event management and registration"""
import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, Boolean, Enum as SQLEnum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.security.types import EncryptedString


class EventStatus(str, enum.Enum):
    """Event status enumeration"""
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Event(Base):
    """Event model for managing PSMC events and meetings
    
    Validates Requirements 6.1, 6.2, 6.3:
    - Stores event details (title, description, dates, location)
    - Tracks event status and participant limits
    - Links to creator for administrative tracking
    """
    __tablename__ = "events"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Event details
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    # Encrypted-at-rest when DB field encryption is enabled (detect-on-read).
    description: Mapped[str | None] = mapped_column(
        EncryptedString,
        nullable=True
    )
    
    # Event timing
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    
    # Event location
    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    
    # Participant management
    max_participants: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )
    
    # Creator relationship
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Assignment relationship (private-event owner). Nullable => public event.
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )
    
    # Event status
    status: Mapped[EventStatus] = mapped_column(
        SQLEnum(EventStatus, name="event_status", native_enum=False),
        nullable=False,
        default=EventStatus.SCHEDULED
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_events_start_date', 'start_date'),
        Index('idx_events_assigned_user', 'assigned_user_id'),
    )
    
    # Relationships
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by], overlaps="events")
    # Assigned user (private-event owner). Explicit foreign_keys disambiguates from the creator FK.
    assigned_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[assigned_user_id]
    )
    registrations: Mapped[list["EventRegistration"]] = relationship(
        "EventRegistration",
        back_populates="event",
        cascade="all, delete-orphan"
    )
    # Multi-user assignment (Requirements: an event can be assigned to several
    # users). An empty collection => public event (visible to everyone). The
    # legacy single ``assigned_user_id`` column is retained for backward
    # compatibility but the assignment source of truth is this collection.
    assignments: Mapped[list["EventAssignment"]] = relationship(
        "EventAssignment",
        back_populates="event",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Event(id={self.id}, title={self.title}, status={self.status})>"


class EventRegistration(Base):
    """Event registration model for tracking participant registrations
    
    Validates Requirements 6.3:
    - Records user registrations for events
    - Tracks registration timestamp
    - Tracks attendance status
    - Ensures unique registration per user per event
    """
    __tablename__ = "event_registrations"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Event relationship
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # User relationship
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Registration timestamp
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Attendance tracking
    attended: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True
    )
    
    # Unique constraint and indexes
    __table_args__ = (
        UniqueConstraint('event_id', 'user_id', name='uq_event_user_registration'),
        Index('idx_registrations_event', 'event_id'),
    )
    
    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="registrations")
    user: Mapped["User"] = relationship("User", overlaps="event_registrations")
    
    def __repr__(self) -> str:
        return f"<EventRegistration(id={self.id}, event_id={self.event_id}, user_id={self.user_id})>"


class EventAssignment(Base):
    """Assignment of an event to a user (many-to-many join table).

    An event can be assigned to multiple users, and a user can be assigned to
    multiple events. When an event has no assignment rows it is considered a
    public event, visible to every authenticated user. Administrators always
    see every event regardless of assignment.
    """
    __tablename__ = "event_assignments"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )

    # Event relationship (cascade delete assignments with the event)
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False
    )

    # Assigned user
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # Timestamp
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # Prevent duplicate assignments and speed up lookups by event / by user.
    __table_args__ = (
        UniqueConstraint('event_id', 'user_id', name='uq_event_user_assignment'),
        Index('idx_assignments_event', 'event_id'),
        Index('idx_assignments_user', 'user_id'),
    )

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="assignments")
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<EventAssignment(id={self.id}, event_id={self.event_id}, user_id={self.user_id})>"

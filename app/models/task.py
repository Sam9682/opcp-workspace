"""Task models for task management and assignment.

Mirrors the Events feature (``app/models/event.py``) with three deltas:
- No ``max_participants`` column and no registration concept.
- A mandatory single ``owner_id`` FK (NOT nullable).
- Assignments are stored in a dedicated join table (``task_assignments``);
  private-by-default visibility is enforced at the router level.
"""
import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Enum as SQLEnum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.security.types import EncryptedString


class TaskStatus(str, enum.Enum):
    """Task status enumeration.

    ``scheduled`` acts as the active/open state, mirroring event semantics.
    """
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Task(Base):
    """Task model for managing work items with a mandatory owner.

    Validates Requirements 6.1, 6.2:
    - Persisted in a dedicated table separate from events.
    - Stores title, description, start/end dates, location, owner (mandatory FK
      to users), creator, status, and timestamps.

    Validates Requirement 3.4:
    - ``owner_id`` is distinct from the multi-user assignee list, and a user may
      be both owner and an assignee.
    """
    __tablename__ = "tasks"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )

    # Task details
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    # Encrypted-at-rest when DB field encryption is enabled (detect-on-read).
    description: Mapped[str | None] = mapped_column(
        EncryptedString,
        nullable=True
    )

    # Task timing
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    # Task location
    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    # Owner relationship (mandatory single owner). NOT nullable.
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    # Creator relationship
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    # Task status
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, name="task_status", native_enum=False),
        nullable=False,
        default=TaskStatus.SCHEDULED
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
        Index('idx_tasks_start_date', 'start_date'),
        Index('idx_tasks_owner', 'owner_id'),
    )

    # Relationships
    # Explicit foreign_keys disambiguate the owner FK from the creator FK.
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    # Multi-user assignment. An empty collection does NOT make a task public;
    # visibility remains limited to the owner and admins (private-by-default).
    assignments: Mapped[list["TaskAssignment"]] = relationship(
        "TaskAssignment",
        back_populates="task",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title={self.title}, status={self.status})>"


class TaskAssignment(Base):
    """Assignment of a task to a user (many-to-many join table).

    A task can be assigned to multiple users, and a user can be assigned to
    multiple tasks. Unlike events, an empty assignment set does NOT make a task
    public; visibility is private-by-default and enforced at the router level.

    Validates Requirement 6.3:
    - Task-to-assignee relationships are stored in a dedicated join structure
      supporting multiple assignees.
    """
    __tablename__ = "task_assignments"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )

    # Task relationship (cascade delete assignments with the task)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
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

    # Prevent duplicate assignments and speed up lookups by task / by user.
    __table_args__ = (
        UniqueConstraint('task_id', 'user_id', name='uq_task_user_assignment'),
        Index('idx_task_assignments_task', 'task_id'),
        Index('idx_task_assignments_user', 'user_id'),
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="assignments")
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<TaskAssignment(id={self.id}, task_id={self.task_id}, user_id={self.user_id})>"

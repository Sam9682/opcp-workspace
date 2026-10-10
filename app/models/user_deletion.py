"""User deletion model for RGPD compliance"""
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ScheduledUserDeletion(Base):
    """Model for tracking scheduled user deletions
    
    Validates Requirement 9.4:
    - Schedules data deletion within 30 days
    - Tracks deletion requests for RGPD compliance
    - Preserves audit trail of deletion requests
    """
    __tablename__ = "scheduled_user_deletions"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # User to be deleted
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True  # Only one deletion request per user
    )
    
    # Deletion scheduling
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc) + timedelta(days=30)
    )
    
    # User information at time of request (for audit)
    user_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    user_full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    def __repr__(self) -> str:
        return f"<ScheduledUserDeletion(user_id={self.user_id}, scheduled_for={self.scheduled_for})>"

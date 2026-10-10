"""Notification models for user notifications and preferences"""
import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.security.types import EncryptedString


class NotificationType(str, enum.Enum):
    """Notification type enumeration"""
    FORUM_REPLY = "forum_reply"
    EVENT_REMINDER = "event_reminder"
    MEMBERSHIP_EXPIRY = "membership_expiry"
    ANNOUNCEMENT = "announcement"
    PAYMENT_CONFIRMATION = "payment_confirmation"


class Notification(Base):
    """Notification model for user notifications
    
    Validates Requirements 10.1, 10.2, 10.3, 10.5:
    - Stores notifications sent to users
    - Tracks notification type and read status
    - Links to user for notification delivery
    """
    __tablename__ = "notifications"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # User relationship
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Notification details
    type: Mapped[NotificationType] = mapped_column(
        SQLEnum(NotificationType, name="notification_type", native_enum=False),
        nullable=False
    )
    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    # Encrypted-at-rest when DB field encryption is enabled (detect-on-read).
    content: Mapped[str] = mapped_column(
        EncryptedString,
        nullable=False
    )
    
    # Read status
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    # Timestamp
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_notifications_user', 'user_id'),
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", overlaps="notifications")
    
    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.type})>"


class NotificationPreferences(Base):
    """Notification preferences model for user notification settings
    
    Validates Requirements 10.4:
    - Stores user preferences for different notification types
    - Allows users to control which notifications they receive
    """
    __tablename__ = "notification_preferences"
    
    # Primary key (user_id is the primary key)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        primary_key=True
    )
    
    # Notification preferences
    email_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    forum_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    event_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    announcement_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", overlaps="notification_preferences")
    
    def __repr__(self) -> str:
        return f"<NotificationPreferences(user_id={self.user_id})>"

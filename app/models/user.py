"""User model for authentication and authorization"""
import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.security.types import EncryptedString


class UserRole(str, enum.Enum):
    """User role enumeration for access control"""
    VISITOR = "visitor"
    MEMBER = "member"
    ADMINISTRATOR = "administrator"


class User(Base):
    """User model with authentication fields
    
    Validates Requirements 2.1, 2.6, 7.1:
    - Stores user authentication information
    - Tracks email verification status
    - Manages user roles for access control
    - Tracks membership expiration dates
    """
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Authentication fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # User information
    # Encrypted-at-rest when DB field encryption is enabled (detect-on-read).
    # Widened to Text because ciphertext exceeds the former 100-char bound.
    first_name: Mapped[str] = mapped_column(
        EncryptedString,
        nullable=False
    )
    last_name: Mapped[str] = mapped_column(
        EncryptedString,
        nullable=False
    )
    
    # Authorization and membership
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role", native_enum=False),
        nullable=False,
        default=UserRole.MEMBER
    )
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    membership_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    membership_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default=None
    )
    
    # Two-factor authentication (2FA)
    totp_secret: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        default=None
    )
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        default=False
    )
    email_2fa_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        default=False
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
    
    # Additional indexes defined at class level
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_role', 'role'),
    )
    
    # Relationships
    topics: Mapped[list["Topic"]] = relationship(
        "Topic",
        back_populates="author",
        cascade="all, delete-orphan"
    )
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="author",
        cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="uploader",
        cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(
        "Event",
        foreign_keys="Event.created_by",
        cascade="all, delete-orphan"
    )
    event_registrations: Mapped[list["EventRegistration"]] = relationship(
        "EventRegistration",
        cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        cascade="all, delete-orphan"
    )
    notification_preferences: Mapped["NotificationPreferences"] = relationship(
        "NotificationPreferences",
        uselist=False,
        cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

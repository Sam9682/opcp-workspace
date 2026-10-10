"""Audit log model for administrative action tracking"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AuditLog(Base):
    """Audit log model for tracking administrative actions
    
    Validates Requirements 7.5:
    - Records all administrative actions with timestamp
    - Tracks admin identity and action details
    - Stores target information for audit trail
    """
    __tablename__ = "audit_log"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Admin relationship (nullable for system events like failed logins)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )
    
    # Action details
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    target_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True
    )
    
    # Additional details stored as JSON
    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )
    
    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_audit_admin', 'admin_id'),
        Index('idx_audit_timestamp', 'timestamp'),
    )
    
    # Relationships
    admin: Mapped["User"] = relationship("User", overlaps="audit_logs")
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, admin_id={self.admin_id}, action={self.action})>"

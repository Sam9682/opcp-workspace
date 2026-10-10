"""Payment model for membership fee processing"""
import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class PaymentMethod(str, enum.Enum):
    """Payment method enumeration"""
    CREDIT_CARD = "credit_card"
    PAYPAL = "paypal"


class PaymentStatus(str, enum.Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(Base):
    """Payment model for membership fees
    
    Validates Requirements 4.2, 4.3:
    - Records payment transactions
    - Stores payment method and status
    - Links to invoice URLs
    - Tracks transaction IDs for reconciliation
    """
    __tablename__ = "payments"
    
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
    
    # Payment details
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="EUR"
    )
    
    # Payment method and status
    payment_method: Mapped[PaymentMethod] = mapped_column(
        SQLEnum(PaymentMethod, name="payment_method", native_enum=False),
        nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus, name="payment_status", native_enum=False),
        nullable=False
    )
    
    # Transaction tracking
    transaction_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True
    )
    
    # Invoice URL
    invoice_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_payments_user', 'user_id'),
        Index('idx_payments_status', 'status'),
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="payments")
    
    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount}, status={self.status})>"

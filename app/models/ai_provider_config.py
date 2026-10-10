"""AI provider enablement configuration model for the AI Oracle page.

Backs the ``ai_provider_config`` table which stores, per AI provider, whether
that provider is offered in the AI Oracle "AI provider" dropdown. One row per
provider id (``shai``, ``kiro``, ``openai``, ``opcp_companion``).

Business rules:
- ``shai`` is always enabled and cannot be turned off (enforced in the service
  and admin layers). Its row exists purely so the table is complete.
- The other providers default to disabled. When disabled they are absent from
  the dropdown entirely (not shown greyed-out).
"""
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from app.database import Base


# Canonical provider ids used across the app (frontend, schemas, factory).
AI_PROVIDER_IDS = ("shai", "kiro", "openai", "opcp_companion")

# Provider that is always enabled and cannot be disabled.
ALWAYS_ENABLED_PROVIDER = "shai"

# Default enablement seeded when no row exists yet.
DEFAULT_PROVIDER_ENABLED = {
    "shai": True,
    "kiro": False,
    "openai": False,
    "opcp_companion": False,
}


class AIProviderConfig(Base):
    """Per-provider enablement flag for the AI Oracle provider dropdown.

    Maps the ``ai_provider_config`` table. The primary key is the provider id
    string so lookups are direct and the set of rows mirrors the known provider
    ids.
    """
    __tablename__ = "ai_provider_config"

    # Canonical provider id (e.g. "shai", "kiro", "openai", "opcp_companion").
    provider: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    # Whether the provider is offered in the AI Oracle dropdown.
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false"
    )

    # Timestamps / editor tracking
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<AIProviderConfig(provider={self.provider!r}, "
            f"enabled={self.enabled})>"
        )

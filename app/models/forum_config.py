"""Forum configuration model for the home page "View" button.

Backs the ``forum_config`` table which stores forum-related feature toggles as
key/value rows. Currently holds a single setting, ``view_button_enabled``,
controlling whether the read-only "View" button is displayed to logged-out
visitors on the home page.

Business rules:
- The setting uses non-inverted semantics: ``enabled=True`` means the button is
  shown, ``enabled=False`` means it is hidden.
- When no row exists the setting defaults to ON (see ``DEFAULT_FORUM_CONFIG``),
  preserving today's behavior.
"""
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from app.database import Base


# Canonical setting key for the home page "View" button toggle.
FORUM_VIEW_BUTTON_KEY = "view_button_enabled"

# Default configuration seeded when no row exists yet (button shown by default).
DEFAULT_FORUM_CONFIG = {"view_button_enabled": True}


class ForumConfig(Base):
    """Per-setting enablement flag for forum features.

    Maps the ``forum_config`` table. The primary key is the setting key string
    so lookups are direct and the set of rows mirrors the known setting keys.
    """
    __tablename__ = "forum_config"

    # Canonical setting key (e.g. "view_button_enabled").
    key: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    # Whether the associated forum feature is enabled.
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true"
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
            f"<ForumConfig(key={self.key!r}, "
            f"enabled={self.enabled})>"
        )

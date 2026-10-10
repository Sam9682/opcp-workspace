"""Service helpers for the home page "View" button toggle.

Centralises reading and writing the ``view_button_enabled`` flag stored in the
``forum_config`` table so both the public forum router (which exposes the flag
to logged-out visitors) and the admin router (which edits it) share one source
of truth.

Business rules enforced here:
- The setting uses non-inverted semantics: ``True`` means the button is shown.
- When no row exists the setting falls back to ``DEFAULT_FORUM_CONFIG`` (True),
  preserving today's behavior.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.forum_config import (
    ForumConfig,
    FORUM_VIEW_BUTTON_KEY,
    DEFAULT_FORUM_CONFIG,
)


def get_view_button_enabled(db: Session) -> bool:
    """Return whether the home page "View" button is currently enabled.

    Falls back to ``DEFAULT_FORUM_CONFIG["view_button_enabled"]`` (True) when no
    row exists yet.
    """
    row = (
        db.query(ForumConfig)
        .filter(ForumConfig.key == FORUM_VIEW_BUTTON_KEY)
        .first()
    )
    if row is None:
        return DEFAULT_FORUM_CONFIG["view_button_enabled"]
    return bool(row.enabled)


def set_view_button_enabled(
    db: Session,
    enabled: bool,
    updated_by: Optional[UUID] = None,
) -> bool:
    """Persist the "View" button enablement flag.

    Upserts the ``view_button_enabled`` row, commits, then re-reads and returns
    the resulting value. Follows the upsert + commit + re-read shape of
    ``set_enabled_map``.
    """
    now = datetime.now(timezone.utc)

    row = (
        db.query(ForumConfig)
        .filter(ForumConfig.key == FORUM_VIEW_BUTTON_KEY)
        .first()
    )
    if row is None:
        row = ForumConfig(key=FORUM_VIEW_BUTTON_KEY)
        db.add(row)
    row.enabled = bool(enabled)
    row.updated_at = now
    row.updated_by = updated_by

    db.commit()
    return get_view_button_enabled(db)

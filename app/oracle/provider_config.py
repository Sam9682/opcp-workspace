"""Service helpers for AI Oracle provider enablement.

Centralises reading and writing the per-provider ``enabled`` flags stored in
the ``ai_provider_config`` table so both the Oracle router (which exposes the
enabled providers to the dropdown) and the admin router (which edits them) share
one source of truth.

Business rules enforced here:
- ``shai`` is always reported as enabled and cannot be disabled.
- Providers with no row yet fall back to ``DEFAULT_PROVIDER_ENABLED`` (only
  ``shai`` defaults to enabled).
"""
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ai_provider_config import (
    AIProviderConfig,
    AI_PROVIDER_IDS,
    ALWAYS_ENABLED_PROVIDER,
    DEFAULT_PROVIDER_ENABLED,
)


def get_enabled_map(db: Session) -> Dict[str, bool]:
    """Return the enabled flag for every known provider id.

    Falls back to defaults for any provider missing a row, and forces
    ``shai`` to always be enabled regardless of what is stored.
    """
    rows = db.query(AIProviderConfig).all()
    stored = {row.provider: bool(row.enabled) for row in rows}

    result: Dict[str, bool] = {}
    for provider_id in AI_PROVIDER_IDS:
        if provider_id == ALWAYS_ENABLED_PROVIDER:
            result[provider_id] = True
        else:
            result[provider_id] = stored.get(
                provider_id, DEFAULT_PROVIDER_ENABLED[provider_id]
            )
    return result


def is_provider_enabled(db: Session, provider_id: str) -> bool:
    """Whether a single provider is currently enabled."""
    return get_enabled_map(db).get(provider_id, False)


def set_enabled_map(
    db: Session,
    updates: Dict[str, bool],
    updated_by: Optional[UUID] = None,
) -> Dict[str, bool]:
    """Persist enablement flags for the given providers.

    ``shai`` is ignored for disabling: it is always kept enabled. Unknown
    provider ids are ignored. Returns the resulting enabled map.
    """
    now = datetime.now(timezone.utc)
    for provider_id, enabled in updates.items():
        if provider_id not in AI_PROVIDER_IDS:
            continue
        # shai can never be disabled.
        effective = True if provider_id == ALWAYS_ENABLED_PROVIDER else bool(enabled)

        row = (
            db.query(AIProviderConfig)
            .filter(AIProviderConfig.provider == provider_id)
            .first()
        )
        if row is None:
            row = AIProviderConfig(provider=provider_id)
            db.add(row)
        row.enabled = effective
        row.updated_at = now
        row.updated_by = updated_by

    db.commit()
    return get_enabled_map(db)

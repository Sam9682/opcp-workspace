"""Service helpers for the ``encryption_config`` single-row table.

Centralises reading and writing the database-field-encryption state so the
admin router, the ``EncryptedString`` type, and the offline migration script
share one source of truth. Mirrors the upsert + commit + re-read shape of
``app/forum/config_service.py``.

Business rules enforced here:
- The ``enabled`` flag defaults to False (plaintext) when no row exists.
- Setting a password key stores only a random salt and the salted verification
  hash; the key itself is never persisted.
- ``verify_password_key`` validates a supplied key against the stored hash.
- ``set_enabled`` flips the flag (used by the migration script after the data
  has actually been encrypted/decrypted).

A tiny process-level cache backs :func:`is_encryption_enabled_cached` so the
``EncryptedString`` type can check the flag on every bind/result without a DB
round-trip per row. The cache is invalidated whenever the flag is written.
"""
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.encryption_config import (
    EncryptionConfig,
    ENCRYPTION_CONFIG_KEY,
    DEFAULT_ENCRYPTION_CONFIG,
)
from app.security import encryption


# ---------------------------------------------------------------------------
# Cached enabled-flag accessor (used by the EncryptedString type).
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 5.0
_cache_lock = threading.RLock()
_cached_enabled: Optional[bool] = None
_cached_at: float = 0.0


def _invalidate_cache() -> None:
    global _cached_enabled, _cached_at
    with _cache_lock:
        _cached_enabled = None
        _cached_at = 0.0


def is_encryption_enabled_cached(db: Session) -> bool:
    """Return the enabled flag, using a short-lived process cache.

    Falls back to a DB read when the cache is cold or stale. Safe to call on a
    per-row basis from the ``EncryptedString`` type.
    """
    global _cached_enabled, _cached_at
    now = time.monotonic()
    with _cache_lock:
        if _cached_enabled is not None and (now - _cached_at) < _CACHE_TTL_SECONDS:
            return _cached_enabled
    value = get_encryption_enabled(db)
    with _cache_lock:
        _cached_enabled = value
        _cached_at = now
    return value


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------
def _get_row(db: Session) -> Optional[EncryptionConfig]:
    return (
        db.query(EncryptionConfig)
        .filter(EncryptionConfig.key == ENCRYPTION_CONFIG_KEY)
        .first()
    )


def get_encryption_enabled(db: Session) -> bool:
    """Return whether field encryption is enabled (default False)."""
    row = _get_row(db)
    if row is None:
        return DEFAULT_ENCRYPTION_CONFIG["enabled"]
    return bool(row.enabled)


def key_is_set(db: Session) -> bool:
    """Return True iff an administrator has set a password key."""
    row = _get_row(db)
    return bool(row and row.verification_hash and row.salt)


def get_config(db: Session) -> dict:
    """Return a non-secret summary of the encryption configuration.

    Never includes the verification hash or salt — only booleans safe to
    expose to the admin UI.
    """
    row = _get_row(db)
    if row is None:
        return {"enabled": DEFAULT_ENCRYPTION_CONFIG["enabled"], "key_is_set": False}
    return {
        "enabled": bool(row.enabled),
        "key_is_set": bool(row.verification_hash and row.salt),
    }


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------
def _ensure_row(db: Session) -> EncryptionConfig:
    row = _get_row(db)
    if row is None:
        row = EncryptionConfig(key=ENCRYPTION_CONFIG_KEY, enabled=False)
        db.add(row)
    return row


def set_verification(
    db: Session,
    password_key: str,
    updated_by: Optional[UUID] = None,
) -> dict:
    """Store the salted verification hash for ``password_key``.

    Generates a fresh salt and persists the salt + verification hash. Does NOT
    change the ``enabled`` flag (that is the migration script's job). Returns
    the non-secret config summary.
    """
    salt = encryption.generate_salt()
    verification_hash = encryption.compute_verification_hash(password_key, salt)

    row = _ensure_row(db)
    row.salt = _b64(salt)
    row.verification_hash = verification_hash
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = updated_by
    db.commit()
    return get_config(db)


def verify_password_key(db: Session, password_key: str) -> bool:
    """Return True iff ``password_key`` matches the stored verification hash.

    Returns False when no key has been set yet.
    """
    row = _get_row(db)
    if not row or not row.verification_hash or not row.salt:
        return False
    salt = _unb64(row.salt)
    return encryption.verify_key(password_key, salt, row.verification_hash)


def derive_fernet_key(db: Session, password_key: str) -> bytes:
    """Derive the Fernet key for ``password_key`` using the stored salt.

    Caller must have validated the key via :func:`verify_password_key` first.
    Raises ``ValueError`` if no salt has been set.
    """
    row = _get_row(db)
    if not row or not row.salt:
        raise ValueError("No encryption salt configured; set a password key first")
    salt = _unb64(row.salt)
    return encryption.derive_key(password_key, salt)


def set_enabled(
    db: Session,
    enabled: bool,
    updated_by: Optional[UUID] = None,
) -> bool:
    """Flip the enabled flag and return the resulting value.

    Invoked by the offline migration script only after the on-disk data has
    actually been encrypted/decrypted. Invalidates the enabled-flag cache.
    """
    row = _ensure_row(db)
    row.enabled = bool(enabled)
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = updated_by
    db.commit()
    _invalidate_cache()
    return get_encryption_enabled(db)


# ---------------------------------------------------------------------------
# base64 helpers (salt is stored urlsafe-base64 encoded)
# ---------------------------------------------------------------------------
import base64  # noqa: E402  (kept local to this module's concern)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("utf-8"))

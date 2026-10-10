"""Database field encryption configuration model.

Backs the ``encryption_config`` table which stores, as a single key/value row,
whether application-level field encryption is enabled plus the salted
verification hash used to validate the administrator's password key.

Business rules:
- A single canonical row keyed by ``ENCRYPTION_CONFIG_KEY``.
- ``enabled`` defaults to False (data stored in plaintext) so existing
  deployments are unaffected until an administrator opts in.
- ``verification_hash`` / ``salt`` are NULL until an administrator sets a
  password key. The password key itself is never stored; only the salted
  PBKDF2 hash is persisted so a supplied key can be validated but not
  recovered.
- The ``enabled`` flag is only flipped by the offline migration script once all
  in-scope rows have been encrypted/decrypted, so the flag and the on-disk data
  stay consistent.
"""
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from app.database import Base


# Canonical single-row key for the encryption configuration.
ENCRYPTION_CONFIG_KEY = "db_field_encryption"

# Default configuration when no row exists yet (encryption OFF).
DEFAULT_ENCRYPTION_CONFIG = {"enabled": False}


class EncryptionConfig(Base):
    """Single-row configuration for database field encryption.

    Maps the ``encryption_config`` table. The primary key is the setting key
    string (mirrors ``forum_config``) so lookups are direct.
    """
    __tablename__ = "encryption_config"

    # Canonical setting key (always ``ENCRYPTION_CONFIG_KEY``).
    key: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    # Whether field encryption is currently active for on-disk data.
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false"
    )

    # Salted PBKDF2 verification hash of the password key (urlsafe-base64).
    # NULL until an administrator sets a key.
    verification_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None
    )

    # Random salt (urlsafe-base64) used for key derivation and the verification
    # hash. NULL until an administrator sets a key.
    salt: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None
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
            f"<EncryptionConfig(key={self.key!r}, "
            f"enabled={self.enabled}, key_is_set={self.verification_hash is not None})>"
        )

"""Process-level holder for the active database-encryption Fernet key.

The derived Fernet key lives only in memory for the lifetime of the process. It
is never written to the database (only a verification hash is persisted). The
provider can be seeded at startup from the ``DB_ENCRYPTION_KEY`` environment
variable, or populated at runtime when an administrator supplies and validates
the password key via the admin API.

When the provider is *inactive* (no key), :class:`EncryptedString` stores and
returns values as plaintext and never attempts to decrypt. This keeps the app
functional (in a plaintext-only mode) even if encryption is enabled but the key
has not yet been supplied after a restart.
"""
import threading
from typing import Optional

__all__ = ["KeyProvider", "key_provider"]


class KeyProvider:
    """Thread-safe, in-memory holder for the active Fernet key.

    The key is a Fernet key (urlsafe-base64-encoded 32 bytes) as produced by
    :func:`app.security.encryption.derive_key`.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._key: Optional[bytes] = None

    def set_key(self, fernet_key: bytes) -> None:
        """Install the active Fernet key for this process."""
        if not fernet_key:
            raise ValueError("fernet_key must be a non-empty bytes value")
        with self._lock:
            self._key = fernet_key

    def get_key(self) -> Optional[bytes]:
        """Return the active Fernet key, or ``None`` when inactive."""
        with self._lock:
            return self._key

    def is_active(self) -> bool:
        """Return True iff a key is currently loaded."""
        with self._lock:
            return self._key is not None

    def clear(self) -> None:
        """Remove the active key (the provider becomes inactive)."""
        with self._lock:
            self._key = None


# Process-wide singleton used by the EncryptedString type and the admin API.
key_provider = KeyProvider()


def seed_from_environment() -> bool:
    """Seed the singleton provider from ``DB_ENCRYPTION_KEY`` if present.

    The environment variable holds a ready-to-use Fernet key (as emitted by
    :func:`app.security.encryption.derive_key`). Returns True if a key was
    loaded, False when the variable is empty/absent.

    Imported lazily inside the function to avoid a circular import between
    ``app.config`` and this module at import time.
    """
    from app.config import settings

    raw = (settings.DB_ENCRYPTION_KEY or "").strip()
    if not raw:
        return False
    key_provider.set_key(raw.encode("utf-8"))
    return True

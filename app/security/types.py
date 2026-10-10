"""``EncryptedString`` SQLAlchemy type for transparent field encryption.

Wraps a ``Text`` column so that:

- **On write** (``process_bind_param``): if the process has an active
  encryption key loaded (:data:`app.security.key_provider.key_provider`), the
  value is encrypted with Fernet before being stored. Otherwise the plaintext
  is stored unchanged. The key is loaded only when encryption is enabled and an
  administrator has supplied the password key, so "key active" is the practical
  signal that new data should be encrypted.

- **On read** (``process_result_value``): the stored value is inspected. If a
  key is active and the value decrypts as a Fernet token, the plaintext is
  returned. Values that are not valid ciphertext (legacy plaintext, or data
  written while encryption was off) are returned unchanged.

This "detect-on-read" behaviour is what makes the mixed state during migration
safe: a table may contain a blend of plaintext and ciphertext rows and every
row still reads back correctly. Because the SQL type is ``Text``, the decorator
is a drop-in on both PostgreSQL and the SQLite test harness.

Encryption is non-deterministic, so columns using this type must never appear
in ``WHERE`` / ``ORDER BY`` / ``UNIQUE`` clauses.
"""
from typing import Optional

from sqlalchemy.types import TypeDecorator, Text

from app.security import encryption
from app.security.key_provider import key_provider

__all__ = ["EncryptedString"]

# Fernet tokens are urlsafe-base64 and always start with the version byte
# 0x80, which base64-encodes to the "gAAAAA" prefix. Used as a cheap pre-check
# before attempting a (more expensive, exception-raising) decrypt.
_FERNET_PREFIX = "gAAAAA"


class EncryptedString(TypeDecorator):
    """Transparently encrypt/decrypt a text column when a key is active."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """Encrypt on write when a key is active; otherwise store plaintext."""
        if value is None:
            return None
        key = key_provider.get_key()
        if key is None:
            # Encryption inactive -> store plaintext (feature off, or key not
            # yet supplied after a restart).
            return value
        # Avoid double-encrypting a value that is already a Fernet token.
        if self._looks_encrypted(value):
            return value
        return encryption.encrypt(value, key)

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """Decrypt on read when the value is ciphertext; else pass through."""
        if value is None:
            return None
        key = key_provider.get_key()
        if key is None:
            # No key loaded -> cannot decrypt; return the raw stored value.
            return value
        if not self._looks_encrypted(value):
            # Legacy / plaintext row written while encryption was off.
            return value
        try:
            return encryption.decrypt(value, key)
        except encryption.InvalidToken:
            # Not actually our ciphertext (e.g. plaintext that happens to start
            # with the prefix) -> return unchanged rather than raising.
            return value

    @staticmethod
    def _looks_encrypted(value: str) -> bool:
        """Cheap heuristic: does this look like a Fernet token?"""
        return value.startswith(_FERNET_PREFIX)

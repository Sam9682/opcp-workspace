"""Cryptographic primitives for database field encryption.

The administrator supplies a password key. From that key (plus a per-config
random salt) we derive:

- A **Fernet encryption key** via PBKDF2-HMAC-SHA256. Used to encrypt/decrypt
  in-scope database columns. Never persisted.
- A **verification hash** via PBKDF2-HMAC-SHA256 under a different info/context
  so it is cryptographically independent of the encryption key. Persisted so
  the app can validate a supplied password key without being able to recover
  the key itself.

Security properties:
- The password key is never logged and never persisted in recoverable form.
- Fernet provides authenticated encryption; ``decrypt`` raises
  ``cryptography.fernet.InvalidToken`` on a wrong key or tampered ciphertext.
- Key derivation is deterministic for a given (password key, salt) pair, so a
  restored key reproduces the same Fernet key and verification hash.
"""
import base64
import hashlib
import hmac
import os

from cryptography.fernet import Fernet, InvalidToken

__all__ = [
    "InvalidToken",
    "generate_salt",
    "derive_key",
    "compute_verification_hash",
    "verify_key",
    "encrypt",
    "decrypt",
]

# PBKDF2 iteration count. High enough to be costly to brute force, cheap enough
# that a one-time key setup / verify stays responsive.
_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16

# Distinct context prefixes so the encryption key and the verification hash are
# derived independently from the same password key + salt.
_ENC_CONTEXT = b"opcp-db-encryption-key-v1:"
_VERIFY_CONTEXT = b"opcp-db-encryption-verify-v1:"


def generate_salt() -> bytes:
    """Return a fresh cryptographically-random salt."""
    return os.urandom(_SALT_BYTES)


def _pbkdf2(password_key: str, salt: bytes, context: bytes) -> bytes:
    """Derive 32 raw bytes from the password key, salt, and a context prefix."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        context + password_key.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
        dklen=32,
    )


def derive_key(password_key: str, salt: bytes) -> bytes:
    """Derive a Fernet-compatible key from the password key and salt.

    Returns a urlsafe-base64-encoded 32-byte key suitable for
    :class:`cryptography.fernet.Fernet`. Deterministic for a given input pair.
    """
    raw = _pbkdf2(password_key, salt, _ENC_CONTEXT)
    return base64.urlsafe_b64encode(raw)


def compute_verification_hash(password_key: str, salt: bytes) -> str:
    """Compute the persisted verification hash for a password key.

    Independent of :func:`derive_key` (different context prefix), so storing the
    hash does not weaken the encryption key.
    """
    raw = _pbkdf2(password_key, salt, _VERIFY_CONTEXT)
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def verify_key(password_key: str, salt: bytes, stored_hash: str) -> bool:
    """Return True iff ``password_key`` reproduces ``stored_hash`` for ``salt``.

    Uses a constant-time comparison to avoid timing side channels.
    """
    candidate = compute_verification_hash(password_key, salt)
    return hmac.compare_digest(candidate, stored_hash)


def encrypt(plaintext: str, key: bytes) -> str:
    """Encrypt a plaintext string, returning a Fernet token string.

    ``key`` must be a Fernet key as produced by :func:`derive_key`.
    """
    token = Fernet(key).encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt(token: str, key: bytes) -> str:
    """Decrypt a Fernet token back to the original plaintext.

    Raises :class:`cryptography.fernet.InvalidToken` if ``token`` was produced
    under a different key or has been tampered with.
    """
    plaintext = Fernet(key).decrypt(token.encode("utf-8"))
    return plaintext.decode("utf-8")

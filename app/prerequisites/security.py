"""Secret encryption helpers for prerequisite credential storage.

The OpenStack application-credential secret is stored write-only: the plaintext
exists only transiently in memory during a save/retrieve call, and only the
Fernet ciphertext is persisted. The symmetric key is derived from
``settings.SECRET_KEY`` so no additional key material has to be provisioned.

Plaintext secrets are never logged; ciphertext is the only persisted form.
"""
import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _fernet() -> Fernet:
    """Build a :class:`Fernet` instance from a key derived from SECRET_KEY.

    Fernet requires a urlsafe-base64-encoded 32-byte key. We derive that key
    deterministically by hashing ``settings.SECRET_KEY`` with SHA-256 (which
    always yields 32 bytes) and base64url-encoding the digest.
    """
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret, returning a Fernet token string.

    The returned ciphertext is the only value that should ever be persisted.
    """
    token = _fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a Fernet token back to the original plaintext secret.

    Raises ``cryptography.fernet.InvalidToken`` if the ciphertext has been
    tampered with or was produced under a different SECRET_KEY (rotation).
    """
    plaintext = _fernet().decrypt(ciphertext.encode("utf-8"))
    return plaintext.decode("utf-8")

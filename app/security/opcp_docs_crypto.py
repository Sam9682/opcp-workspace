"""Encryption primitives for the OPCP reference documentation files.

The files under ``docs/opcp_external_docs`` are stored encrypted in the
repository. Each encrypted file keeps its original name and has this layout::

    OPCP-ENCRYPTED:v1:<base64url salt>\\n
    <Fernet token>\\n

The Fernet key is derived from a passphrase (``KEY_DECRYPT_INFORMATIONS_OPCP``)
with PBKDF2-HMAC-SHA256 and the salt stored in the header. The derived key is
cached per (passphrase, salt), so decrypting many files encrypted in one run
(which share a salt) costs a single derivation.

This module has no dependency on the application settings so that it can be
used by the standalone script ``scripts/opcp_docs_crypto.py``.
"""
from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

__all__ = [
    "MAGIC",
    "InvalidToken",
    "is_encrypted",
    "encrypt_bytes",
    "decrypt_bytes",
    "new_salt",
]

MAGIC = b"OPCP-ENCRYPTED:v1:"
_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16


def new_salt() -> bytes:
    """Return a fresh random salt."""
    return os.urandom(_SALT_BYTES)


@lru_cache(maxsize=16)
def _derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    raw = hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, _PBKDF2_ITERATIONS, dklen=32
    )
    return base64.urlsafe_b64encode(raw)


def is_encrypted(data: bytes) -> bool:
    """True if ``data`` is an encrypted OPCP document (header check only)."""
    return data.startswith(MAGIC)


def encrypt_bytes(plaintext: bytes, passphrase: str, salt: Optional[bytes] = None) -> bytes:
    """Encrypt ``plaintext`` into the encrypted-document format."""
    if not passphrase:
        raise ValueError("An encryption passphrase is required")
    salt = salt if salt is not None else new_salt()
    token = Fernet(_derive_fernet_key(passphrase, salt)).encrypt(plaintext)
    return MAGIC + base64.urlsafe_b64encode(salt) + b"\n" + token + b"\n"


def decrypt_bytes(data: bytes, passphrase: str) -> bytes:
    """Decrypt an encrypted document.

    Raises ``ValueError`` if ``data`` is not in the encrypted format and
    ``cryptography.fernet.InvalidToken`` if the passphrase is wrong or the
    content was tampered with.
    """
    if not is_encrypted(data):
        raise ValueError("Data is not an encrypted OPCP document")
    header, _, token = data.partition(b"\n")
    try:
        salt = base64.urlsafe_b64decode(header[len(MAGIC):])
    except (ValueError, TypeError) as exc:
        raise ValueError("Malformed encrypted OPCP document header") from exc
    return Fernet(_derive_fernet_key(passphrase, salt)).decrypt(token.strip())

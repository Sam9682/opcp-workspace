"""Unit tests for the encryption primitives (Task 1) and KeyProvider (Task 2).

Covers key derivation, verification hashing, Fernet encrypt/decrypt round-trips,
wrong-key rejection, and the in-memory KeyProvider lifecycle.
"""
import pytest

from app.security import encryption
from app.security.key_provider import KeyProvider


# ---------------------------------------------------------------------------
# Task 1: encryption primitives
# ---------------------------------------------------------------------------
def test_encrypt_decrypt_round_trip():
    """A value encrypted with a derived key decrypts back to the original."""
    salt = encryption.generate_salt()
    key = encryption.derive_key("correct horse battery staple", salt)
    plaintext = "sensitive forum content \u00e9\u00e8\u00e0"  # includes non-ascii

    token = encryption.encrypt(plaintext, key)

    assert token != plaintext
    assert encryption.decrypt(token, key) == plaintext


def test_key_derivation_is_deterministic():
    """Same password key + salt derive the same Fernet key."""
    salt = encryption.generate_salt()
    k1 = encryption.derive_key("pw", salt)
    k2 = encryption.derive_key("pw", salt)
    assert k1 == k2


def test_key_derivation_varies_with_salt_and_password():
    """Different salt or password yields a different key."""
    s1 = encryption.generate_salt()
    s2 = encryption.generate_salt()
    assert encryption.derive_key("pw", s1) != encryption.derive_key("pw", s2)
    assert encryption.derive_key("pw", s1) != encryption.derive_key("other", s1)


def test_verification_hash_accepts_correct_key():
    """verify_key returns True for the password used to compute the hash."""
    salt = encryption.generate_salt()
    stored = encryption.compute_verification_hash("pw", salt)
    assert encryption.verify_key("pw", salt, stored) is True


def test_verification_hash_rejects_wrong_key():
    """verify_key returns False for a different password."""
    salt = encryption.generate_salt()
    stored = encryption.compute_verification_hash("pw", salt)
    assert encryption.verify_key("wrong", salt, stored) is False


def test_verification_hash_independent_of_encryption_key():
    """The verification hash is not equal to the encryption key material."""
    salt = encryption.generate_salt()
    stored = encryption.compute_verification_hash("pw", salt)
    key = encryption.derive_key("pw", salt).decode("utf-8")
    assert stored != key


def test_decrypt_wrong_key_raises_invalid_token():
    """Decrypting with a key derived from a different password raises."""
    salt = encryption.generate_salt()
    key = encryption.derive_key("pw", salt)
    wrong = encryption.derive_key("nope", salt)
    token = encryption.encrypt("secret", key)
    with pytest.raises(encryption.InvalidToken):
        encryption.decrypt(token, wrong)


# ---------------------------------------------------------------------------
# Task 2: KeyProvider
# ---------------------------------------------------------------------------
def test_key_provider_starts_inactive():
    kp = KeyProvider()
    assert kp.is_active() is False
    assert kp.get_key() is None


def test_key_provider_set_get_clear():
    kp = KeyProvider()
    key = encryption.derive_key("pw", encryption.generate_salt())
    kp.set_key(key)
    assert kp.is_active() is True
    assert kp.get_key() == key
    kp.clear()
    assert kp.is_active() is False
    assert kp.get_key() is None


def test_key_provider_rejects_empty_key():
    kp = KeyProvider()
    with pytest.raises(ValueError):
        kp.set_key(b"")

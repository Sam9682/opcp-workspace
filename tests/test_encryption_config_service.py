"""Tests for the encryption_config model, service, and EncryptedString type.

Covers Task 3 (EncryptedString detect-on-read behaviour) and Task 4 (config
service: default-off, set/verify key, flag flip). Uses the in-memory SQLite
``db_session`` fixture from tests/conftest.py.
"""
import pytest

from app.models import EncryptionConfig, ENCRYPTION_CONFIG_KEY
from app.security import config_service
from app.security import encryption
from app.security.key_provider import key_provider
from app.security.types import EncryptedString


@pytest.fixture(autouse=True)
def _clear_key_provider():
    """Ensure the global key provider is inactive around each test."""
    key_provider.clear()
    config_service._invalidate_cache()
    yield
    key_provider.clear()
    config_service._invalidate_cache()


# ---------------------------------------------------------------------------
# Task 4: config service
# ---------------------------------------------------------------------------
def test_default_off_when_no_row(db_session):
    assert db_session.query(EncryptionConfig).count() == 0
    assert config_service.get_encryption_enabled(db_session) is False
    assert config_service.key_is_set(db_session) is False
    assert config_service.get_config(db_session) == {"enabled": False, "key_is_set": False}


def test_set_and_verify_password_key(db_session):
    summary = config_service.set_verification(db_session, "s3cret-key")
    assert summary == {"enabled": False, "key_is_set": True}
    assert config_service.key_is_set(db_session) is True

    assert config_service.verify_password_key(db_session, "s3cret-key") is True
    assert config_service.verify_password_key(db_session, "wrong") is False


def test_verify_false_when_no_key_set(db_session):
    assert config_service.verify_password_key(db_session, "anything") is False


def test_derive_fernet_key_matches_manual_derivation(db_session):
    config_service.set_verification(db_session, "pw")
    row = db_session.query(EncryptionConfig).filter_by(key=ENCRYPTION_CONFIG_KEY).first()
    salt = config_service._unb64(row.salt)
    expected = encryption.derive_key("pw", salt)
    assert config_service.derive_fernet_key(db_session, "pw") == expected


def test_set_enabled_flips_flag(db_session):
    assert config_service.get_encryption_enabled(db_session) is False
    assert config_service.set_enabled(db_session, True) is True
    assert config_service.get_encryption_enabled(db_session) is True
    assert config_service.set_enabled(db_session, False) is False
    assert config_service.get_encryption_enabled(db_session) is False


def test_cached_enabled_accessor(db_session):
    config_service.set_enabled(db_session, True)
    assert config_service.is_encryption_enabled_cached(db_session) is True
    # set_enabled invalidates the cache, so a flip is observed.
    config_service.set_enabled(db_session, False)
    assert config_service.is_encryption_enabled_cached(db_session) is False


# ---------------------------------------------------------------------------
# Task 3: EncryptedString type (detect-on-read)
# ---------------------------------------------------------------------------
def test_bind_stores_plaintext_when_key_inactive():
    t = EncryptedString()
    assert key_provider.is_active() is False
    assert t.process_bind_param("hello", None) == "hello"


def test_bind_encrypts_when_key_active():
    t = EncryptedString()
    key = encryption.derive_key("pw", encryption.generate_salt())
    key_provider.set_key(key)
    stored = t.process_bind_param("hello", None)
    assert stored != "hello"
    assert stored.startswith("gAAAAA")


def test_result_decrypts_ciphertext_when_key_active():
    t = EncryptedString()
    key = encryption.derive_key("pw", encryption.generate_salt())
    key_provider.set_key(key)
    stored = t.process_bind_param("hello", None)
    assert t.process_result_value(stored, None) == "hello"


def test_result_passes_through_plaintext_when_key_active():
    """Legacy plaintext (written while off) reads back unchanged even with a key."""
    t = EncryptedString()
    key_provider.set_key(encryption.derive_key("pw", encryption.generate_salt()))
    assert t.process_result_value("legacy plaintext", None) == "legacy plaintext"


def test_result_returns_ciphertext_raw_when_key_inactive():
    """With no key loaded, ciphertext is returned as-is (cannot decrypt)."""
    t = EncryptedString()
    key = encryption.derive_key("pw", encryption.generate_salt())
    key_provider.set_key(key)
    stored = t.process_bind_param("hello", None)
    key_provider.clear()
    assert t.process_result_value(stored, None) == stored


def test_none_passthrough():
    t = EncryptedString()
    assert t.process_bind_param(None, None) is None
    assert t.process_result_value(None, None) is None


def test_bind_does_not_double_encrypt():
    t = EncryptedString()
    key_provider.set_key(encryption.derive_key("pw", encryption.generate_salt()))
    once = t.process_bind_param("hello", None)
    twice = t.process_bind_param(once, None)
    assert once == twice

"""Property-based test for the credential-secret encryption round-trip.

Feature spec: .kiro/specs/openstack-node-status

Property 1: Secret encryption round-trip
Validates: Requirements 3.2

The OpenStack application-credential secret is stored write-only: only the
Fernet ciphertext is persisted, and the plaintext is recoverable via
``decrypt_secret``. The helpers live in ``app/prerequisites/security.py`` and
derive a symmetric Fernet key from ``settings.SECRET_KEY`` (SHA-256 digest,
base64url-encoded). ``SECRET_KEY`` is supplied to the test environment through
the repository ``.env`` file loaded by ``app.config.Settings``.

This property asserts, for any secret string, that:

- ``decrypt_secret(encrypt_secret(s)) == s`` (lossless round-trip), and
- the ciphertext never equals the plaintext (the secret is genuinely
  transformed, never persisted verbatim).
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.prerequisites.security import decrypt_secret, encrypt_secret


# Application-credential secrets are arbitrary text. Empty strings are a valid
# (if degenerate) secret and are worth covering, so min_size=0. The upper bound
# keeps generated examples reasonable without constraining the property.
_secret = st.text(min_size=0, max_size=512)


@settings(max_examples=200, deadline=None)
@given(secret=_secret)
def test_secret_encryption_round_trip(secret):
    """Feature: openstack-node-status, Property 1: Secret encryption round-trip

    Validates: Requirements 3.2
    """
    ciphertext = encrypt_secret(secret)

    # The round-trip is lossless: decrypting recovers the exact plaintext.
    assert decrypt_secret(ciphertext) == secret, (
        f"round-trip failed for secret {secret!r}: got {decrypt_secret(ciphertext)!r}"
    )

    # The ciphertext must never equal the plaintext: the secret is always
    # transformed before it would be persisted.
    assert ciphertext != secret, (
        f"ciphertext equals plaintext for secret {secret!r}"
    )

"""Unit test for TOTP setup response shape.

Spec: .kiro/specs/account-security (task 3.8)

Validates Requirement 5.1: when the user begins TOTP_2FA setup, the Auth_Backend
generates a TOTP secret for the Current_User and returns a QR-code-compatible
provisioning value and the secret using pyotp. The secret is stored as pending
(``totp_secret`` set) while ``totp_enabled`` stays false until confirmed.
"""
from fastapi import status

from app.models import User


def test_totp_setup_returns_secret_and_uri_and_keeps_disabled(
    client, db_session, test_user, auth_headers
):
    """POST /api/auth/2fa/totp/setup returns ``secret`` + ``otpauth_uri`` and stays pending.

    Requirement 5.1:
    - Response contains a non-empty ``secret``.
    - Response contains a non-empty ``otpauth_uri`` that is an ``otpauth://`` URI.
    - The secret is persisted on the User record.
    - ``totp_enabled`` remains false (pending state, not yet confirmed).
    """
    # Pre-condition: a fresh user has no TOTP secret and TOTP disabled.
    assert test_user.totp_secret is None
    assert test_user.totp_enabled is False

    response = client.post("/api/auth/2fa/totp/setup", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()

    # Response shape: secret and otpauth_uri are present and non-empty.
    assert set(body.keys()) == {"secret", "otpauth_uri"}
    assert isinstance(body["secret"], str) and body["secret"]
    assert isinstance(body["otpauth_uri"], str) and body["otpauth_uri"]

    # The provisioning value is a QR-code-compatible otpauth:// URI that carries
    # the returned secret.
    assert body["otpauth_uri"].startswith("otpauth://")
    assert f"secret={body['secret']}" in body["otpauth_uri"]

    # The secret is persisted on the User record and TOTP remains disabled
    # (pending state until a valid confirmation code arrives).
    persisted = db_session.query(User).filter(User.id == test_user.id).first()
    assert persisted is not None
    assert persisted.totp_secret == body["secret"]
    assert persisted.totp_enabled is False

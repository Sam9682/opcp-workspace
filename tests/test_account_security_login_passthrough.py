"""Unit test for no-2FA login passthrough (backward compatibility).

Task 5.6 / Requirement 7.4: a user with neither TOTP nor Email 2FA enabled
must receive an ``access_token`` directly from ``POST /api/auth/login`` with
no intermediate 2FA challenge step, preserving the pre-2FA login behavior.
"""
from fastapi import status


def test_login_without_2fa_returns_access_token_directly(client, verified_user):
    """A verified user with no 2FA enabled logs in directly (Requirement 7.4).

    Asserts the login response carries an ``access_token`` and does NOT signal
    a second-step challenge (no ``requires_2fa`` / ``challenge_token``).
    """
    # Sanity: the fixture user has no 2FA method enabled.
    assert verified_user.totp_enabled is False
    assert verified_user.email_2fa_enabled is False

    response = client.post(
        "/api/auth/login",
        json={"email": verified_user.email, "password": "SecurePass123"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Passthrough: a session token is issued immediately.
    assert "access_token" in data
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == verified_user.email

    # No 2FA challenge step is triggered.
    assert "requires_2fa" not in data
    assert "challenge_token" not in data

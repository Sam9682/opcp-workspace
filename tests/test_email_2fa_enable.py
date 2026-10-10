"""Unit test for email-2FA enable persistence.

Spec: .kiro/specs/account-security (task 3.7)

Validates Requirement 6.1: when the user enables Email_2FA, the Auth_Backend
enables Email_2FA for the Current_User and persists the associated field on the
User record.
"""
from fastapi import status

from app.models import User


def test_email_2fa_enable_persists_true(client, db_session, test_user, auth_headers):
    """POST /api/auth/2fa/email/enable persists ``email_2fa_enabled=True``.

    Requirement 6.1: enabling email 2FA sets ``email_2fa_enabled`` to true on the
    User record and the response reflects the enabled state.
    """
    # Pre-condition: email 2FA is not enabled for the fresh user.
    assert test_user.email_2fa_enabled is False

    response = client.post("/api/auth/2fa/email/enable", headers=auth_headers)

    # Response reflects the enabled state (Requirement 6.1).
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"email_2fa_enabled": True}

    # The change is persisted on the User record.
    persisted = db_session.query(User).filter(User.id == test_user.id).first()
    assert persisted is not None
    assert persisted.email_2fa_enabled is True

"""Unit test for change-password audit logging.

Feature: account-security
Task 2.3 - Write unit test for change-password audit logging.

Validates Requirement 3.6:
- WHEN a password change is applied, the Change_Password_Endpoint records the
  event in the Audit_Log.
"""
import pytest
from fastapi import status
from app.models import User, UserRole, AuditLog
from app.auth.password import hash_password, verify_password


@pytest.fixture
def security_user(db_session):
    """Create a verified user with a known password for change-password tests."""
    user = User(
        email="change-pw@example.com",
        password_hash=hash_password("CurrentPass123"),
        first_name="Change",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def security_headers(client, security_user):
    """Log in the security user and return authenticated request headers."""
    response = client.post(
        "/api/auth/login",
        json={"email": security_user.email, "password": "CurrentPass123"},
    )
    assert response.status_code == status.HTTP_200_OK
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_change_password_writes_audit_log(client, security_user, security_headers, db_session):
    """A successful password change writes a PASSWORD_CHANGED audit log row.

    Validates Requirement 3.6.
    """
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": "CurrentPass123", "new_password": "BrandNewPass456"},
        headers=security_headers,
    )

    assert response.status_code == status.HTTP_200_OK

    # An AuditLog row with action PASSWORD_CHANGED exists for this user.
    audit_log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "PASSWORD_CHANGED",
            AuditLog.admin_id == security_user.id,
        )
        .first()
    )
    assert audit_log is not None
    assert audit_log.target_id == security_user.id

    # Sanity check the change was actually applied.
    db_session.refresh(security_user)
    assert verify_password("BrandNewPass456", security_user.password_hash)


def test_change_password_failure_writes_no_audit_log(client, security_user, security_headers, db_session):
    """A failed password change (wrong current password) writes no audit row.

    Guards Requirement 3.6 against false positives: the audit event is recorded
    only when a password change is actually applied.
    """
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": "WrongCurrent123", "new_password": "BrandNewPass456"},
        headers=security_headers,
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    audit_log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "PASSWORD_CHANGED",
            AuditLog.admin_id == security_user.id,
        )
        .first()
    )
    assert audit_log is None

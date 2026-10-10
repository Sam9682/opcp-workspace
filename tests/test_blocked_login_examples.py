"""Example/integration tests for the membership gate on the login() path.

Feature: expired-user-login-block
Task 3.3 - Write example/integration tests for the login path.

These example-based (not property) tests exercise the real ``/api/auth/login``
endpoint through the FastAPI TestClient against the SQLite test DB, covering the
specific wiring of the membership gate inserted in ``login()`` (task 3.1):

- Blocked user (``expired`` and ``suspended``): no token issued, HTTP 401
  ``INVALID_CREDENTIALS``, and an ``AuditLog`` with action ``LOGIN_FAILED``.
- ``active`` user with a *past* ``membership_expires_at``: still allowed. This
  confirms the gate reads the stored status directly and never recomputes
  status from the expiry date (no recomputation).
- Unknown status string and ``null``: allowed, the existing flow continues.

Validates: Requirements 1.1, 1.3, 1.5, 2.1, 2.2
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status

from app.models import User, UserRole, AuditLog
from app.auth.password import hash_password
from app.auth.rate_limiter import login_rate_limiter


_PASSWORD = "SecurePass123"


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset the login rate limiter around each test so attempts don't bleed."""
    login_rate_limiter._attempts.clear()
    yield
    login_rate_limiter._attempts.clear()


def _make_user(
    db_session,
    email,
    membership_status,
    membership_expires_at=None,
):
    """Persist a verified member with the given membership fields."""
    user = User(
        email=email,
        password_hash=hash_password(_PASSWORD),
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True,
        membership_status=membership_status,
        membership_expires_at=membership_expires_at,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login(client, email):
    return client.post("/api/auth/login", json={"email": email, "password": _PASSWORD})


# ---------------------------------------------------------------------------
# Blocked statuses: expired and suspended are denied (Req 1.1, 3.1, 4.1).
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize("blocked_status", ["expired", "suspended"])
def test_login_blocked_membership_denied(client, db_session, blocked_status):
    """A blocked membership gets no token, a generic 401, and a LOGIN_FAILED audit.

    Validates Requirements 1.1 (deny + no token).
    """
    user = _make_user(db_session, f"{blocked_status}@example.com", blocked_status)

    response = _login(client, user.email)

    # Denied with the generic invalid-credentials response — no token issued.
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    body = response.json()
    error = body["error"]
    assert error["code"] == "INVALID_CREDENTIALS"
    assert error["message"] == "Invalid email or password"
    assert error["details"] == {}
    assert "access_token" not in body
    assert "requires_2fa" not in body

    # A LOGIN_FAILED audit record is persisted for the blocked attempt.
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.action == "LOGIN_FAILED",
        AuditLog.admin_id == user.id,
    ).first()
    assert audit_log is not None
    assert audit_log.details["reason"] == "membership_blocked"


# ---------------------------------------------------------------------------
# No recomputation from the date: active + past expiry still logs in
# (Req 2.1, 2.2).
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_login_active_with_past_expiry_still_allowed(client, db_session):
    """An ``active`` user with a past ``membership_expires_at`` still logs in.

    The gate reads the stored status directly and never derives blocked status
    from the expiry date. Validates Requirements 2.1, 2.2.
    """
    past = datetime.now(timezone.utc) - timedelta(days=365)
    user = _make_user(
        db_session,
        "active-past-expiry@example.com",
        membership_status="active",
        membership_expires_at=past,
    )

    response = _login(client, user.email)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == user.email

    # Successful (not blocked) — a LOGIN_SUCCESS audit, no membership block.
    success_log = db_session.query(AuditLog).filter(
        AuditLog.action == "LOGIN_SUCCESS",
        AuditLog.admin_id == user.id,
    ).first()
    assert success_log is not None

    blocked_log = db_session.query(AuditLog).filter(
        AuditLog.action == "LOGIN_FAILED",
        AuditLog.admin_id == user.id,
    ).first()
    assert blocked_log is None


# ---------------------------------------------------------------------------
# Non-blocked statuses continue the existing flow (Req 1.3, 1.5).
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_login_unknown_status_allowed(client, db_session):
    """An unknown status string is not in the block-list, so login proceeds.

    Validates Requirements 1.5 (any value other than blocked continues).
    """
    user = _make_user(db_session, "unknown-status@example.com", "frozen")

    response = _login(client, user.email)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == user.email


@pytest.mark.integration
def test_login_null_status_allowed(client, db_session):
    """A null membership_status is allowed; the existing flow continues.

    Validates Requirements 1.5 (null continues the existing flow).
    """
    user = _make_user(db_session, "null-status@example.com", membership_status=None)

    response = _login(client, user.email)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == user.email


@pytest.mark.integration
@pytest.mark.parametrize("allowed_status", ["pending", "active"])
def test_login_pending_and_active_allowed(client, db_session, allowed_status):
    """``pending`` and ``active`` continue the existing authentication flow.

    Validates Requirements 1.3 (pending/active continue the flow).
    """
    user = _make_user(db_session, f"{allowed_status}@example.com", allowed_status)

    response = _login(client, user.email)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == user.email

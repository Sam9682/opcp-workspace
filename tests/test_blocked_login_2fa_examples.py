"""Example/integration tests for the membership gate on the login_2fa() path.

Feature: expired-user-login-block
Task 4.4 - Write example/integration tests for the 2FA path.

These example-based (not property) tests exercise the real
``/api/auth/login/2fa`` endpoint through the FastAPI TestClient against the
SQLite test DB, covering the specific wiring of the membership gate inserted in
``login_2fa()`` (task 4.1). The gate runs *after* the submitted code is
validated and immediately before the session token is issued, so:

- Blocked user (``expired`` and ``suspended``) presenting a *valid* code: no
  token issued, HTTP 401 ``INVALID_CREDENTIALS``, and an ``AuditLog`` with
  action ``LOGIN_2FA_FAILED`` and ``reason == "membership_blocked"``.
- ``active`` / ``pending`` / ``null`` with a valid code: the existing flow
  continues and a session token is issued.
- ``INVALID_2FA_CODE`` behavior is unchanged: a blocked user who submits an
  *invalid* code still gets the existing ``INVALID_2FA_CODE`` error, proving
  the membership gate runs only after code validation (never short-circuiting
  the invalid-code path to the generic credentials error).

Each test drives the real two-step email-2FA flow: ``POST /api/auth/login``
returns a short-lived challenge token and "emails" a 6-digit code (captured by
patching ``email_service.send_2fa_code_email``), then ``POST
/api/auth/login/2fa`` submits that challenge token with a code.

The blocked-user tests obtain the challenge while the user is ``active`` and
then persist the blocked status before the second step. This is required
because the sibling gate in ``login()`` (task 3.1) already denies a blocked
user at the first step, so no challenge token would ever be issued for a user
that is blocked up front. The challenge token is independent of membership
status, so flipping the stored status before the second step isolates and
exercises exactly the ``login_2fa()`` gate under test.

Validates: Requirements 1.2, 1.4, 1.5, 3.2
"""
import pytest
from fastapi import status

from app.auth.password import hash_password
from app.auth.rate_limiter import login_rate_limiter
from app.middleware.rate_limit import limiter
from app.models import AuditLog, User, UserRole
from app.services.email import email_service


_PASSWORD = "SecurePass123"


@pytest.fixture(autouse=True)
def _rate_limits_off():
    """Disable the per-email and slowapi rate limiters around each test.

    The two-step flow hits ``/login`` then ``/login/2fa``; disabling both
    limiters keeps the example tests independent of abuse-protection budgets
    that are not under test. State is restored afterward.
    """
    previous = limiter.enabled
    limiter.enabled = False
    login_rate_limiter._attempts.clear()
    try:
        yield
    finally:
        limiter.enabled = previous
        login_rate_limiter._attempts.clear()


def _make_email_2fa_user(db_session, email, membership_status):
    """Persist a verified member with Email 2FA enabled (no TOTP).

    Email 2FA keeps the code deterministic and capturable, so the "valid code"
    branch of ``/login/2fa`` can be driven reliably in an example test.
    """
    user = User(
        email=email,
        password_hash=hash_password(_PASSWORD),
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True,
        totp_enabled=False,
        email_2fa_enabled=True,
        membership_status=membership_status,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _set_membership_status(db_session, user, membership_status):
    """Update the stored membership status for an existing user and persist."""
    user.membership_status = membership_status
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _start_challenge(client, monkeypatch, email):
    """Drive ``POST /api/auth/login`` and capture the emailed 2FA code.

    Returns ``(challenge_token, captured_code)``. Asserts the login step issues
    a challenge (never a direct token) for an Email-2FA user.
    """
    captured = {}

    def _capture(to_email, code, user_name):
        captured["code"] = code
        return True

    monkeypatch.setattr(email_service, "send_2fa_code_email", _capture)

    resp = client.post(
        "/api/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    # An Email-2FA user must get a challenge, never a direct token: this is the
    # precondition that lets us reach login_2fa() with a valid code.
    assert body.get("requires_2fa") is True, body
    assert "access_token" not in body, body
    assert "code" in captured, "send_2fa_code_email was not invoked"
    return body["challenge_token"], captured["code"]


# ---------------------------------------------------------------------------
# Blocked statuses: a valid 2FA code is still denied (Req 1.2, 3.2, 4.2).
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize("blocked_status", ["expired", "suspended"])
def test_login_2fa_blocked_membership_denied(
    client, db_session, monkeypatch, blocked_status
):
    """A blocked membership with a valid code gets no token and a 401.

    The gate in ``login_2fa()`` denies the attempt with the generic
    invalid-credentials response and persists a ``LOGIN_2FA_FAILED`` audit.
    Validates Requirements 1.2, 3.2.

    The challenge is first obtained while the user is ``active`` because the
    sibling gate in ``login()`` (task 3.1) would otherwise deny the first step
    and no challenge token would ever be issued. We then persist the blocked
    status before the second step so the ``login_2fa()`` gate is the thing
    under test. The challenge token is independent of membership status, so
    this exercises exactly the 2FA-path gate.
    """
    user = _make_email_2fa_user(
        db_session, f"2fa-{blocked_status}@example.com", "active"
    )

    challenge_token, valid_code = _start_challenge(client, monkeypatch, user.email)

    # Flip to the blocked status now that we hold a valid challenge token.
    _set_membership_status(db_session, user, blocked_status)

    resp = client.post(
        "/api/auth/login/2fa",
        json={"challenge_token": challenge_token, "code": valid_code},
    )

    # Denied with the generic invalid-credentials response — no token issued.
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED, resp.text
    body = resp.json()
    error = body["error"]
    assert error["code"] == "INVALID_CREDENTIALS"
    assert error["message"] == "Invalid email or password"
    assert error["details"] == {}
    assert "access_token" not in body

    # A LOGIN_2FA_FAILED audit record (reason=membership_blocked) is persisted.
    db_session.expire_all()
    audit_log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "LOGIN_2FA_FAILED",
            AuditLog.admin_id == user.id,
            AuditLog.details["reason"].as_string() == "membership_blocked",
        )
        .first()
    )
    assert audit_log is not None
    assert audit_log.details["reason"] == "membership_blocked"


# ---------------------------------------------------------------------------
# Allowed statuses: a valid 2FA code still issues a session token
# (Req 1.4, 1.5).
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize("allowed_status", ["active", "pending", None])
def test_login_2fa_allowed_membership_issues_token(
    client, db_session, monkeypatch, allowed_status
):
    """``active`` / ``pending`` / ``null`` with a valid code issue a token.

    The membership gate does not block, so the existing 2FA success flow
    continues. Validates Requirements 1.4 (pending/active) and 1.5 (null).
    """
    label = allowed_status if allowed_status is not None else "null"
    user = _make_email_2fa_user(
        db_session, f"2fa-{label}@example.com", allowed_status
    )

    challenge_token, valid_code = _start_challenge(client, monkeypatch, user.email)

    resp = client.post(
        "/api/auth/login/2fa",
        json={"challenge_token": challenge_token, "code": valid_code},
    )

    assert resp.status_code == status.HTTP_200_OK, resp.text
    data = resp.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == user.email

    # No membership-block audit was recorded for an allowed status.
    db_session.expire_all()
    blocked_log = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "LOGIN_2FA_FAILED",
            AuditLog.admin_id == user.id,
        )
        .first()
    )
    assert blocked_log is None


# ---------------------------------------------------------------------------
# INVALID_2FA_CODE is unchanged: the gate runs only after code validation.
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_login_2fa_invalid_code_blocked_user_keeps_invalid_2fa_code(
    client, db_session, monkeypatch
):
    """A blocked user with an *invalid* code still gets ``INVALID_2FA_CODE``.

    Because the membership gate runs only after the submitted code is
    validated, an invalid code is rejected on the existing code-validation path
    (``INVALID_2FA_CODE``) and never reaches the generic membership-block
    denial. This proves the gate did not change the invalid-code behavior.
    Validates Requirement 3.2 (and the design's "unchanged INVALID_2FA_CODE").
    """
    # Obtain the challenge while active (the login() gate would otherwise deny
    # the first step), then flip to a blocked status so the user IS blocked at
    # the 2FA step. The invalid code must still win: the gate runs only after
    # code validation, so it is never reached here.
    user = _make_email_2fa_user(
        db_session, "2fa-invalid-blocked@example.com", "active"
    )

    challenge_token, valid_code = _start_challenge(client, monkeypatch, user.email)

    _set_membership_status(db_session, user, "expired")

    # Submit a code guaranteed NOT to match the captured one.
    wrong_code = "000000" if valid_code != "000000" else "111111"

    resp = client.post(
        "/api/auth/login/2fa",
        json={"challenge_token": challenge_token, "code": wrong_code},
    )

    # Existing invalid-code behavior: INVALID_2FA_CODE, not the membership
    # block's INVALID_CREDENTIALS.
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED, resp.text
    body = resp.json()
    assert body["error"]["code"] == "INVALID_2FA_CODE"
    assert "access_token" not in body

    # The failure recorded is the invalid-code one (no membership_blocked
    # reason), confirming the gate was never reached.
    db_session.expire_all()
    failed_logs = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "LOGIN_2FA_FAILED",
            AuditLog.admin_id == user.id,
        )
        .all()
    )
    assert failed_logs, "an invalid-code failure must be audited"
    assert all(
        log.details.get("reason") != "membership_blocked" for log in failed_logs
    )


@pytest.mark.integration
def test_login_2fa_invalid_code_allowed_user_keeps_invalid_2fa_code(
    client, db_session, monkeypatch
):
    """An allowed user with an invalid code also gets ``INVALID_2FA_CODE``.

    Confirms the invalid-code path is unchanged independently of membership
    status (the gate is purely additive on the success path).
    """
    user = _make_email_2fa_user(
        db_session, "2fa-invalid-active@example.com", "active"
    )

    challenge_token, valid_code = _start_challenge(client, monkeypatch, user.email)

    wrong_code = "000000" if valid_code != "000000" else "111111"

    resp = client.post(
        "/api/auth/login/2fa",
        json={"challenge_token": challenge_token, "code": wrong_code},
    )

    assert resp.status_code == status.HTTP_401_UNAUTHORIZED, resp.text
    body = resp.json()
    assert body["error"]["code"] == "INVALID_2FA_CODE"
    assert "access_token" not in body

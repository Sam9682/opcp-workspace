"""Property-based test for Email 2FA login enforcement.

Feature spec: .kiro/specs/account-security

Property 4: Email 2FA login enforcement
Validates: Requirements 7.2, 7.3

For a login by a user with Email 2FA enabled, given the 6-digit code delivered
in the challenge, the second step (``POST /api/auth/login/2fa``) issues a
session token *if and only if* the submitted code matches the challenge code
within its validity window; otherwise it returns a verification error and no
token.

How this exercises the real behavior
-------------------------------------
The test drives the actual endpoints in ``app/auth/router.py``:

1. ``email_service.send_2fa_code_email`` is patched so the 6-digit code the
   ``/login`` handler generates and "emails" is captured instead of sent. The
   handler embeds only the SHA-256 hash of that code (``code_hash``) in a
   short-lived ``2fa_challenge`` JWT (Requirement 7.2).
2. ``POST /api/auth/login`` with valid primary credentials returns the
   ``requires_2fa`` challenge and its ``challenge_token``.
3. ``POST /api/auth/login/2fa`` is called with the challenge token and either
   the captured (valid) code or an arbitrary submitted code, asserting a
   session token is issued *iff* the submitted code matches the captured code
   (Requirements 7.2, 7.3).

The single ``@given`` property below covers both branches of the biconditional
(matching → token; non-matching → verification error, no token). Keeping it to
one property function means the app lifespan / test database are opened once for
the whole run rather than repeatedly, which keeps the many-iteration run
reliable on this suite's file-backed SQLite test database.

Rate limits (the per-email ``login_rate_limiter`` and the slowapi ``20/hour`` on
``/login/2fa``) are reset before each Hypothesis example so 100+ iterations can
run against the genuine endpoints without tripping abuse protections that are
not part of the property under test.

Tag: Feature: account-security, Property 4: Email 2FA login enforcement
"""
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from fastapi import status

import app.main as app_main
from app.models import User, UserRole
from app.auth.password import hash_password
from app.auth.rate_limiter import login_rate_limiter
from app.middleware.rate_limit import limiter
from app.services.email import email_service


# Arbitrary submitted codes: any string within the schema's 1..10 char range
# (Login2FARequest.code Field(min_length=1, max_length=10)). Bias toward
# 6-digit numeric strings so the "matching" branch is exercised frequently, and
# occasionally emit the whitespace-padded genuine code so the ``.strip()``
# behavior of the handler is covered as well.
_submitted_code = st.one_of(
    st.integers(min_value=0, max_value=999_999).map(lambda n: f"{n:06d}"),
    st.text(min_size=1, max_size=10),
)

_EMAIL = "email2fa@example.com"
_PASSWORD = "SecurePass123"


@pytest.fixture(autouse=True)
def _quiet_background_scheduler(monkeypatch):
    """Stop the app's periodic background scheduler thread during the test.

    The app lifespan starts a background APScheduler thread whose jobs run
    against the configured database. Over a many-iteration Hypothesis run that
    thread can fire mid-example and raise intermittently, leaking
    nondeterminism that Hypothesis flags as a flaky replay. Neutralizing only
    the scheduler's ``start`` (leaving all database wiring untouched) removes
    that noise without changing the endpoint behavior under test. This autouse
    fixture is set up before the ``client`` fixture enters the app lifespan.
    """
    monkeypatch.setattr(app_main.task_scheduler, "start", lambda *a, **k: None)
    yield


def _reset_limiters():
    """Clear both rate limiters so many iterations run against real endpoints."""
    login_rate_limiter._attempts.clear()
    limiter.reset()


def _ensure_email_2fa_user(db_session):
    """Create (or reset) a verified user with Email 2FA enabled and no TOTP.

    Idempotent within the test-database session so it can be called on every
    Hypothesis example without duplicate-email errors.
    """
    user = db_session.query(User).filter(User.email == _EMAIL).first()
    if user is None:
        user = User(
            email=_EMAIL,
            password_hash=hash_password(_PASSWORD),
            first_name="Email2FA",
            last_name="User",
            role=UserRole.MEMBER,
            is_email_verified=True,
        )
        db_session.add(user)
    # Enforce the exact 2FA configuration under test.
    user.email_2fa_enabled = True
    user.totp_enabled = False
    user.totp_secret = None
    db_session.commit()
    db_session.refresh(user)
    return user


def _start_login_challenge(client, monkeypatch):
    """Drive ``POST /api/auth/login`` and capture the emailed 2FA code.

    Returns ``(challenge_token, captured_code)``.
    """
    captured = {}

    def _capture(to_email, code, user_name):
        captured["code"] = code
        return True

    monkeypatch.setattr(email_service, "send_2fa_code_email", _capture)

    resp = client.post(
        "/api/auth/login", json={"email": _EMAIL, "password": _PASSWORD}
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    # Email 2FA user must get a challenge, never a direct token (Req 7.2).
    assert body.get("requires_2fa") is True, body
    assert "email" in body.get("methods", []), body
    assert "access_token" not in body, body
    assert "code" in captured, "send_2fa_code_email was not invoked"
    return body["challenge_token"], captured["code"]


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(submitted=_submitted_code)
def test_email_2fa_login_issues_token_iff_code_matches(
    client, db_session, monkeypatch, submitted
):
    """Feature: account-security, Property 4: Email 2FA login enforcement

    Validates: Requirements 7.2, 7.3

    For an Email-2FA login, ``/login/2fa`` issues a session token iff the
    submitted code matches the code delivered in the challenge; otherwise it
    returns a verification error and no token.
    """
    _reset_limiters()
    _ensure_email_2fa_user(db_session)

    challenge_token, captured_code = _start_login_challenge(client, monkeypatch)

    # Ground truth: the second step should succeed exactly when the submitted
    # code matches the emailed code (compared after stripping, mirroring the
    # handler's ``_hash_2fa_code`` which strips before hashing).
    should_succeed = submitted.strip() == captured_code.strip()

    resp = client.post(
        "/api/auth/login/2fa",
        json={"challenge_token": challenge_token, "code": submitted},
    )

    if should_succeed:
        # Matching code → session token issued (Req 7.2).
        assert resp.status_code == status.HTTP_200_OK, resp.text
        body = resp.json()
        assert body.get("access_token"), body
        assert body.get("token_type") == "bearer", body
    else:
        # Non-matching code → verification error, no token (Req 7.3).
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED, resp.text
        body = resp.json()
        assert "access_token" not in body, body

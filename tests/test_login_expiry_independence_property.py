"""Property-based test for expiry-independence of the membership gate (task 4.3).

Feature spec: .kiro/specs/expired-user-login-block

Property 4: Blocking depends only on stored status, not expiry date

For any user whose stored ``membership_status`` is in the allowed set, the gate
SHALL allow authentication regardless of the value of ``membership_expires_at``
(including dates in the past); and for any user whose stored
``membership_status`` is blocked, the gate SHALL block regardless of
``membership_expires_at`` (including dates in the future).

Feature: expired-user-login-block, Property 4: Blocking depends only on stored status, not expiry date

Validates: Requirements 2.1, 2.2

Design notes
------------
This property proves the gate reads the stored ``membership_status`` value
directly and never recomputes status from ``membership_expires_at``. To make
that unambiguous, every example sets ``membership_expires_at`` to the OPPOSITE
of what the status would naively imply:

- An ALLOWED status (``active``/``pending``/``null``/unknown) is paired with a
  PAST ``membership_expires_at``. If the gate wrongly recomputed from the date
  it would block; the correct behavior is to authenticate.
- A BLOCKED status (``expired``/``suspended``) is paired with a FUTURE
  ``membership_expires_at``. If the gate wrongly recomputed from the date it
  would allow; the correct behavior is to block.

Both token-issuing paths are covered:

- ``login()`` — a user with no 2FA reaches the token path directly, so
  ``POST /api/auth/login`` returns a token for allowed users and the generic
  401 for blocked users.
- ``login_2fa()`` — a user with Email 2FA enabled first obtains a challenge
  from ``POST /api/auth/login`` (which requires an allowed status to issue the
  challenge), after which the stored status is updated and the second step
  ``POST /api/auth/login/2fa`` is driven with the matching code. The gate in
  ``login_2fa()`` runs after code validation and immediately before the token
  is issued, so this exercises the 2FA-path gate specifically.

Test harness note
-----------------
``@given`` runs many examples inside a SINGLE test-function invocation, so the
database must stay stable across every example. This module builds its own
dedicated in-memory SQLite engine backed by ``StaticPool`` so all connections
(fixture writes and endpoint reads) share one durable schema for the module's
lifetime. Each example is self-isolating: it creates a fresh user (unique
email), drives the endpoints, asserts, then deletes the user and its audit rows
so state never leaks between examples. ``/login`` and ``/login/2fa`` carry rate
limiters, so the ``rate_limits_off`` fixture disables them for the run and
restores them afterward. Function-scoped-fixture health checks are suppressed
as recommended by Hypothesis for this pattern.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.password import hash_password
from app.auth.rate_limiter import login_rate_limiter
from app.auth.router import BLOCKED_MEMBERSHIP_STATUSES
from app.database import Base, get_db
from app.main import app
from app.middleware.rate_limit import limiter
from app.models import AuditLog, User, UserRole
from app.services.email import email_service

# A single known primary password reused across examples (primary-credential
# validity is a precondition of the property, not the thing under test).
PRIMARY_PASSWORD = "SecurePass123"

# Dedicated in-memory engine for this module. ``StaticPool`` + a single shared
# connection keeps one durable schema alive for every session/connection, which
# is what a long ``@given`` loop needs (file-backed SQLite was flaky here).
_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(scope="module")
def _schema():
    """Create the schema once for the module on the in-memory engine."""
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture()
def db_session(_schema):
    """A session bound to the module's in-memory engine."""
    session = _TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """Test client whose ``get_db`` yields the same in-memory session.

    Using one session for both fixture writes and endpoint reads guarantees the
    login endpoints resolve freshly created users.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def rate_limits_off():
    """Disable both rate limiters so the property can run many iterations."""
    previous = limiter.enabled
    limiter.enabled = False
    login_rate_limiter._attempts.clear()
    try:
        yield
    finally:
        limiter.enabled = previous
        login_rate_limiter._attempts.clear()


_PAST = datetime(2000, 1, 1, tzinfo=timezone.utc)
_FUTURE = datetime(2999, 1, 1, tzinfo=timezone.utc)


def _make_user(db, membership_status, membership_expires_at, email_2fa=False):
    """Create a fresh verified user with valid credentials.

    ``email_2fa`` selects which path the user exercises: ``False`` → no 2FA so
    the ``login()`` token path is reached directly; ``True`` → Email 2FA so a
    challenge is issued and the ``login_2fa()`` path is exercised. The varied
    fields under test are ``membership_status`` and ``membership_expires_at``.
    """
    user = User(
        # Non-reserved domain: the login step validates the address via
        # pydantic ``EmailStr`` (email-validator), which rejects reserved TLDs.
        email=f"expiry-indep-{uuid.uuid4().hex}@example.com",
        password_hash=hash_password(PRIMARY_PASSWORD),
        first_name="Expiry",
        last_name="Indep",
        role=UserRole.MEMBER,
        is_email_verified=True,
        totp_enabled=False,
        email_2fa_enabled=email_2fa,
        membership_status=membership_status,
        membership_expires_at=membership_expires_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _cleanup_user(db, user_id):
    """Remove the user and any audit rows written for it during this example."""
    db.query(AuditLog).filter(AuditLog.admin_id == user_id).delete(
        synchronize_session=False
    )
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()


def _assert_blocked_login_response(resp, body, db, user_id, action):
    """Assert a blocked-denial 401 + persisted audit record for ``user_id``."""
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED, resp.text
    error = body.get("error", {})
    assert error.get("code") == "INVALID_CREDENTIALS", body
    assert "access_token" not in body
    assert "challenge_token" not in body
    db.expire_all()
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.admin_id == user_id, AuditLog.action == action)
        .first()
    )
    assert audit is not None, f"blocked denial must persist a {action} AuditLog"
    assert audit.details.get("reason") == "membership_blocked"


# Allowed statuses span the full allowed space: the plausible domain values
# (``active``/``pending``), null, the empty string, and arbitrary free-form
# text outside the blocked set. Blocked statuses are exactly the block-list.
_allowed_status = st.one_of(
    st.none(),
    st.sampled_from(["active", "pending", "unknown", ""]),
    st.text(max_size=20).filter(lambda s: s not in BLOCKED_MEMBERSHIP_STATUSES),
)
_blocked_status = st.sampled_from(sorted(BLOCKED_MEMBERSHIP_STATUSES))


# ---------------------------------------------------------------------------
# login() path
# ---------------------------------------------------------------------------
@pytest.mark.property
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(allowed_status=_allowed_status, blocked_status=_blocked_status)
def test_login_path_gate_ignores_expiry_date(
    client, db_session, allowed_status, blocked_status
):
    """Feature: expired-user-login-block, Property 4: Blocking depends only on
    stored status, not expiry date (login path).

    An allowed status with a PAST expiry still authenticates; a blocked status
    with a FUTURE expiry is still blocked. Validates Requirements 2.1, 2.2.
    """
    # Allowed status + PAST expiry -> must authenticate (no recomputation).
    allowed_user = _make_user(db_session, allowed_status, _PAST, email_2fa=False)
    allowed_id = allowed_user.id
    try:
        resp = client.post(
            "/api/auth/login",
            json={"email": allowed_user.email, "password": PRIMARY_PASSWORD},
        )
        body = resp.json()
        assert resp.status_code == status.HTTP_200_OK, (
            f"allowed status {allowed_status!r} with past expiry must authenticate "
            f"-> {resp.status_code}: {resp.text[:200]}"
        )
        assert body.get("access_token"), body
        assert body.get("token_type") == "bearer", body
    finally:
        _cleanup_user(db_session, allowed_id)

    # Blocked status + FUTURE expiry -> must still be blocked.
    blocked_user = _make_user(db_session, blocked_status, _FUTURE, email_2fa=False)
    blocked_id = blocked_user.id
    try:
        resp = client.post(
            "/api/auth/login",
            json={"email": blocked_user.email, "password": PRIMARY_PASSWORD},
        )
        body = resp.json()
        _assert_blocked_login_response(
            resp, body, db_session, blocked_id, "LOGIN_FAILED"
        )
    finally:
        _cleanup_user(db_session, blocked_id)


# ---------------------------------------------------------------------------
# login_2fa() path
# ---------------------------------------------------------------------------
def _start_email_2fa_challenge(client, monkeypatch, email):
    """Drive ``POST /api/auth/login`` for an Email-2FA user and capture the code.

    Returns ``(challenge_token, captured_code)``. The user must have an allowed
    status at this point for the challenge to be issued (the login() gate runs
    before the challenge branch).
    """
    captured = {}

    def _capture(to_email, code, user_name):
        captured["code"] = code
        return True

    monkeypatch.setattr(email_service, "send_2fa_code_email", _capture)

    resp = client.post(
        "/api/auth/login", json={"email": email, "password": PRIMARY_PASSWORD}
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    assert body.get("requires_2fa") is True, body
    assert "email" in body.get("methods", []), body
    assert "code" in captured, "send_2fa_code_email was not invoked"
    return body["challenge_token"], captured["code"]


@pytest.mark.property
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(allowed_status=_allowed_status, blocked_status=_blocked_status)
def test_login_2fa_path_gate_ignores_expiry_date(
    client, db_session, monkeypatch, allowed_status, blocked_status
):
    """Feature: expired-user-login-block, Property 4: Blocking depends only on
    stored status, not expiry date (2FA path).

    An allowed status with a PAST expiry still issues a token after a valid
    code; a blocked status with a FUTURE expiry is still blocked by the
    login_2fa() gate even with a valid code. Validates Requirements 2.1, 2.2.
    """
    # --- Allowed status + PAST expiry -> valid code issues a token. ---
    allowed_user = _make_user(db_session, allowed_status, _PAST, email_2fa=True)
    allowed_id = allowed_user.id
    try:
        challenge_token, code = _start_email_2fa_challenge(
            client, monkeypatch, allowed_user.email
        )
        resp = client.post(
            "/api/auth/login/2fa",
            json={"challenge_token": challenge_token, "code": code},
        )
        body = resp.json()
        assert resp.status_code == status.HTTP_200_OK, (
            f"allowed status {allowed_status!r} with past expiry must issue a token "
            f"on the 2FA path -> {resp.status_code}: {resp.text[:200]}"
        )
        assert body.get("access_token"), body
        assert body.get("token_type") == "bearer", body
    finally:
        _cleanup_user(db_session, allowed_id)

    # --- Blocked status + FUTURE expiry -> blocked at the login_2fa() gate. ---
    # Start from an allowed status so the challenge is issued, then update the
    # stored status to a blocked value (future expiry) before the second step so
    # the login_2fa() gate itself does the blocking after code validation.
    blocked_user = _make_user(db_session, "active", _FUTURE, email_2fa=True)
    blocked_id = blocked_user.id
    try:
        challenge_token, code = _start_email_2fa_challenge(
            client, monkeypatch, blocked_user.email
        )
        # Flip to a blocked status with a FUTURE expiry; the gate must ignore
        # the date and block on the stored status alone.
        blocked_user.membership_status = blocked_status
        blocked_user.membership_expires_at = _FUTURE
        db_session.commit()

        resp = client.post(
            "/api/auth/login/2fa",
            json={"challenge_token": challenge_token, "code": code},
        )
        body = resp.json()
        _assert_blocked_login_response(
            resp, body, db_session, blocked_id, "LOGIN_2FA_FAILED"
        )
    finally:
        _cleanup_user(db_session, blocked_id)

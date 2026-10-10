"""Property-based test for the 2FA-path membership gate (task 4.2).

Feature spec: .kiro/specs/expired-user-login-block

Property 2: 2FA path blocks expired/suspended memberships completely

For any user with a valid 2FA challenge token and a matching verification code
whose stored ``membership_status`` is ``expired`` or ``suspended``, calling
``POST /api/auth/login/2fa`` SHALL issue no session token, SHALL return HTTP 401
with error code ``INVALID_CREDENTIALS``, and SHALL persist an ``AuditLog`` with
action ``LOGIN_2FA_FAILED``.

Feature: expired-user-login-block, Property 2: 2FA path blocks expired/suspended memberships completely

Validates: Requirements 1.2, 3.2, 4.2

Design notes
------------
- The property targets ``login_2fa()`` in isolation. Because the ``/login``
  path's gate fires *before* a 2FA challenge is ever issued (a blocked user
  never receives a ``challenge_token``), the only way to drive the second-step
  handler for a blocked user is to mint a valid ``2fa_challenge`` token
  directly — exactly the token ``/login`` would produce for an email-2FA user:
  ``{sub, type="2fa_challenge", methods=["email"], code_hash=sha256(code)}``.
  This mirrors the real handler's inputs and exercises the genuine code path.
- Users are created with email 2FA enabled and a verified email. The submitted
  code always *matches* the challenge (``code_valid`` is True), so the gate is
  the only thing that can deny a request. A non-blocked user therefore reaches
  the token path; a blocked user is denied by the gate before any token.
- The gate reads the stored ``membership_status`` directly; the generated
  statuses span the blocked set (``expired``/``suspended``) and the allowed
  space (``None``, ``pending``, ``active``, arbitrary strings) so each example
  asserts the correct branch.
- ``/login/2fa`` carries a slowapi IP rate limit (``20/hour``). A property test
  drives it past budget, so the ``rate_limits_off`` fixture disables it for the
  run and restores it afterward.

Test harness note
-----------------
``@given`` runs many examples inside a SINGLE test-function invocation, so the
database must stay stable across every example. This module builds its own
dedicated in-memory SQLite engine backed by ``StaticPool`` so all connections
(fixture writes and endpoint reads) share one durable schema for the module's
lifetime. Each example is self-isolating: it creates a fresh user (unique
email), drives ``/login/2fa``, asserts, then deletes the user and its audit
rows so state never leaks between examples. Function-scoped-fixture health
checks are suppressed as recommended by Hypothesis for this pattern.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from fastapi import status
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.password import hash_password
from app.auth.rate_limiter import login_rate_limiter
from app.auth.router import BLOCKED_MEMBERSHIP_STATUSES, _hash_2fa_code
from app.auth.token import create_access_token
from app.database import Base, get_db
from app.main import app
from app.middleware.rate_limit import limiter
from app.models import AuditLog, User, UserRole

# A single known primary password reused across examples (unused by the 2FA
# handler itself, but set so the user row is realistic).
PRIMARY_PASSWORD = "SecurePass123"

# The matching 2FA verification code embedded (as a hash) in every minted
# challenge token. Code validity is a precondition of Property 2, not the thing
# under test, so a single known 6-digit code is reused and always submitted.
VALID_CODE = "123456"

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

    Using one session for both fixture writes and endpoint reads guarantees
    ``/login/2fa`` resolves freshly created users.
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


def _make_email_2fa_user(db, membership_status):
    """Create a fresh verified user with email 2FA enabled and no TOTP.

    Email 2FA is the method covered by the minted challenge token, so a
    non-blocked user with a matching code reaches the token path.
    ``membership_status`` is the varied field under test.
    """
    user = User(
        # Use a non-reserved domain so any downstream email validation accepts
        # the address.
        email=f"member-2fa-{uuid.uuid4().hex}@example.com",
        password_hash=hash_password(PRIMARY_PASSWORD),
        first_name="Member",
        last_name="TwoFA",
        role=UserRole.MEMBER,
        is_email_verified=True,
        totp_enabled=False,
        totp_secret=None,
        email_2fa_enabled=True,
        membership_status=membership_status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mint_challenge_token(user_id):
    """Build a valid email-2FA challenge token for ``login_2fa()``.

    Mirrors exactly what ``/login`` produces for an email-2FA user: the subject
    claim, the ``2fa_challenge`` type, the ``email`` method, and the SHA-256
    hash of ``VALID_CODE`` so the submitted ``VALID_CODE`` validates.
    """
    return create_access_token(
        data={
            "sub": str(user_id),
            "type": "2fa_challenge",
            "methods": ["email"],
            "code_hash": _hash_2fa_code(VALID_CODE),
        },
        expires_delta=timedelta(minutes=5),
    )


def _cleanup_user(db, user_id):
    """Remove the user and any audit rows written for it during this example."""
    db.query(AuditLog).filter(AuditLog.admin_id == user_id).delete(
        synchronize_session=False
    )
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()


# Status values spanning the blocked set and the allowed space. We draw the
# plausible domain values plus free-form text and ``None`` (null) so the
# generator covers both branches of the gate without special weighting.
_membership_status = st.one_of(
    st.none(),
    st.sampled_from(["expired", "suspended", "pending", "active", "unknown", ""]),
    st.text(max_size=20),
)


@pytest.mark.property
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(membership_status=_membership_status)
def test_login_2fa_blocks_expired_and_suspended_completely(
    client, db_session, membership_status
):
    """Blocked statuses are denied on the 2FA path; allowed statuses succeed.

    Feature: expired-user-login-block, Property 2: 2FA path blocks
    expired/suspended memberships completely.

    Validates: Requirements 1.2, 3.2, 4.2
    """
    blocked = membership_status in BLOCKED_MEMBERSHIP_STATUSES

    user = _make_email_2fa_user(db_session, membership_status)
    user_id = user.id
    try:
        challenge_token = _mint_challenge_token(user_id)
        resp = client.post(
            "/api/auth/login/2fa",
            json={"challenge_token": challenge_token, "code": VALID_CODE},
        )
        body = resp.json()

        if blocked:
            # 401 with the generic INVALID_CREDENTIALS code (Req 1.2, 3.2).
            assert resp.status_code == status.HTTP_401_UNAUTHORIZED, (
                f"blocked status {membership_status!r} -> {resp.status_code}: "
                f"{resp.text[:200]}"
            )
            # The global handler wraps ``ErrorResponse.create`` output under
            # ``error`` at the top level of the response body.
            error = body.get("error", {})
            assert error.get("code") == "INVALID_CREDENTIALS", (
                f"expected INVALID_CREDENTIALS for {membership_status!r}, got {body!r}"
            )

            # No session token issued (Req 1.2) and no account state disclosed.
            assert "access_token" not in body
            assert error.get("details") in (None, {}, [])

            # A LOGIN_2FA_FAILED audit record is persisted for the user (Req 4.2).
            # The code submitted is always valid, so the only LOGIN_2FA_FAILED
            # record on this path is the gate's membership-blocked denial; the
            # ``reason`` detail is asserted in Python (dialect-safe JSON access).
            db_session.expire_all()
            audits = (
                db_session.query(AuditLog)
                .filter(
                    AuditLog.admin_id == user_id,
                    AuditLog.action == "LOGIN_2FA_FAILED",
                )
                .all()
            )
            assert audits, (
                f"blocked status {membership_status!r} must persist a "
                f"LOGIN_2FA_FAILED AuditLog"
            )
            assert any(
                (a.details or {}).get("reason") == "membership_blocked"
                for a in audits
            ), (
                f"blocked status {membership_status!r} LOGIN_2FA_FAILED audit "
                f"must record reason 'membership_blocked'"
            )
        else:
            # Allowed statuses continue the existing flow and issue a token.
            assert resp.status_code == status.HTTP_200_OK, (
                f"allowed status {membership_status!r} -> {resp.status_code}: "
                f"{resp.text[:200]}"
            )
            assert body.get("access_token"), (
                f"allowed status {membership_status!r} must issue a token"
            )
            assert body.get("token_type") == "bearer"
    finally:
        _cleanup_user(db_session, user_id)

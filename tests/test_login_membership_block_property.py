"""Property-based test for the login-path membership gate (task 3.2).

Feature spec: .kiro/specs/expired-user-login-block

Property 1: Login path blocks expired/suspended memberships completely

For any user with otherwise-valid primary credentials and a verified email
whose stored ``membership_status`` is ``expired`` or ``suspended``, calling
``POST /api/auth/login`` SHALL issue no session token (and no 2FA challenge),
SHALL return HTTP 401 with error code ``INVALID_CREDENTIALS``, and SHALL
persist an ``AuditLog`` with action ``LOGIN_FAILED``.

Feature: expired-user-login-block, Property 1: Login path blocks expired/suspended memberships completely

Validates: Requirements 1.1, 3.1, 4.1

Design notes
------------
- The login path is exercised end-to-end over HTTP. Users are created with
  valid primary credentials (known password hashed, email verified) and NO 2FA
  method enabled, so a *non-blocked* user falls through to the token path while
  a *blocked* user is denied by the gate before any token/challenge is issued.
- The gate reads the stored ``membership_status`` directly; the generated
  statuses span the blocked set (``expired``/``suspended``) and the allowed
  space (``None``, ``pending``, ``active``, arbitrary strings) so each example
  asserts the correct branch.
- ``/login`` carries a ``slowapi`` IP rate limit plus a custom per-email
  limiter. A property test drives them past budget, so the ``rate_limits_off``
  fixture disables both for the run and restores them afterward.

Test harness note
-----------------
``@given`` runs many examples inside a SINGLE test-function invocation, so the
database must stay stable across every example. This module builds its own
dedicated in-memory SQLite engine backed by ``StaticPool`` so all connections
(fixture writes and endpoint reads) share one durable schema for the module's
lifetime. Each example is self-isolating: it creates a fresh user (unique
email), drives ``/login``, asserts, then deletes the user and its audit rows so
state never leaks between examples. Function-scoped-fixture health checks are
suppressed as recommended by Hypothesis for this pattern.
"""
import uuid

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
from app.auth.router import BLOCKED_MEMBERSHIP_STATUSES
from app.database import Base, get_db
from app.main import app
from app.middleware.rate_limit import limiter
from app.models import AuditLog, User, UserRole

# A single known primary password reused across examples (primary-credential
# validity is a precondition of Property 1, not the thing under test).
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

    Using one session for both fixture writes and endpoint reads guarantees
    ``/login`` resolves freshly created users.
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


def _make_user(db, membership_status):
    """Create a fresh verified user with valid credentials and no 2FA.

    Primary credentials are valid (``PRIMARY_PASSWORD`` hashed, email verified)
    and no 2FA method is enabled, so a non-blocked user reaches the token path.
    ``membership_status`` is the varied field under test.
    """
    user = User(
        # Use a non-reserved domain: the login step validates the address via
        # pydantic ``EmailStr`` (email-validator), which rejects reserved TLDs.
        email=f"member-login-{uuid.uuid4().hex}@example.com",
        password_hash=hash_password(PRIMARY_PASSWORD),
        first_name="Member",
        last_name="Login",
        role=UserRole.MEMBER,
        is_email_verified=True,
        totp_enabled=False,
        email_2fa_enabled=False,
        membership_status=membership_status,
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
def test_login_blocks_expired_and_suspended_completely(
    client, db_session, membership_status
):
    """Blocked statuses are denied; allowed statuses continue the flow.

    Feature: expired-user-login-block, Property 1: Login path blocks
    expired/suspended memberships completely.

    Validates: Requirements 1.1, 3.1, 4.1
    """
    blocked = membership_status in BLOCKED_MEMBERSHIP_STATUSES

    user = _make_user(db_session, membership_status)
    user_id = user.id
    try:
        resp = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": PRIMARY_PASSWORD},
        )
        body = resp.json()

        if blocked:
            # 401 with the generic INVALID_CREDENTIALS code (Req 1.1, 3.1).
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

            # No session token and no 2FA challenge issued (Req 1.1).
            assert "access_token" not in body
            assert "challenge_token" not in body
            assert body.get("requires_2fa") is None

            # A LOGIN_FAILED audit record is persisted for the user (Req 4.1).
            db_session.expire_all()
            audit = (
                db_session.query(AuditLog)
                .filter(
                    AuditLog.admin_id == user_id,
                    AuditLog.action == "LOGIN_FAILED",
                )
                .first()
            )
            assert audit is not None, (
                f"blocked status {membership_status!r} must persist a "
                f"LOGIN_FAILED AuditLog"
            )
            assert audit.details.get("reason") == "membership_blocked"
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

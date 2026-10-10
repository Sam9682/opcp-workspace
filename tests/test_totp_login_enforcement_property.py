"""Property-based test for TOTP login enforcement (task 5.4).

Feature spec: .kiro/specs/account-security

Property 3: TOTP login enforcement

For any user with valid primary credentials and TOTP 2FA enabled, the second
login step (``POST /api/auth/login/2fa``) issues a session token if and only if
the submitted TOTP code is valid for that user's stored secret; otherwise it
returns a verification error and issues no token.

Feature: account-security, Property 3: TOTP login enforcement

Validates: Requirements 7.1, 7.3

Design notes
------------
- The two-step login is exercised end-to-end over HTTP: ``POST /login`` with
  valid primary credentials returns a ``2fa_challenge`` token (no session token
  yet), then ``POST /login/2fa`` exchanges ``challenge_token`` + code for a
  session token only when the code is valid.
- ``/login`` and ``/login/2fa`` carry ``slowapi`` IP rate limits (20/hour). A
  property test drives them well past that budget, so the ``rate_limits_off``
  fixture disables the ``slowapi`` limiter for the run and clears the custom
  per-email login limiter around it. Both are restored automatically.

Test harness note
-----------------
``@given`` runs many examples inside a SINGLE test-function invocation, so the
database must stay stable across every example (Hypothesis re-executes example
bodies while shrinking). Rather than reuse the conftest's function-scoped,
file-backed SQLite fixtures — which proved flaky under many iterations on this
filesystem — this module builds its own dedicated **in-memory** SQLite engine
backed by ``StaticPool`` so all connections (fixture writes and endpoint reads)
share one durable in-memory schema for the module's lifetime. Each example is
self-isolating: it creates a fresh user (unique email) with TOTP enabled, drives
the two login steps, asserts, then deletes the user and its audit rows so state
never leaks between examples. Function-scoped-fixture health checks are
suppressed as recommended by Hypothesis for this pattern.
"""
import uuid

import pyotp
import pytest
from fastapi.testclient import TestClient
from fastapi import status
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import totp
from app.auth.password import hash_password
from app.auth.rate_limiter import login_rate_limiter
from app.database import Base, get_db
from app.main import app
from app.middleware.rate_limit import limiter
from app.models import AuditLog, User, UserRole

# A single known primary password reused across examples (primary-credential
# validity is a precondition of Property 3, not the thing under test).
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
    ``/login`` and ``/login/2fa`` resolve freshly created users.
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


def _make_totp_user(db, secret: str):
    """Create a fresh verified user with TOTP enabled and a known password.

    Primary credentials are valid (``PRIMARY_PASSWORD`` hashed, email verified)
    and only TOTP 2FA is enabled — no email 2FA — so ``/login`` returns a pure
    TOTP challenge.
    """
    user = User(
        # Use a non-reserved domain: the primary /login step validates the
        # address via pydantic ``EmailStr`` (email-validator), which rejects
        # reserved TLDs such as ``.test``.
        email=f"totp-login-{uuid.uuid4().hex}@example.com",
        password_hash=hash_password(PRIMARY_PASSWORD),
        first_name="Totp",
        last_name="Login",
        role=UserRole.MEMBER,
        is_email_verified=True,
        totp_secret=secret,
        totp_enabled=True,
        email_2fa_enabled=False,
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


def _login_get_challenge(client, email):
    """Run the primary login step and return the 2FA challenge token.

    Asserts the primary step does NOT issue a session token and that the
    challenge covers the TOTP method (Requirement 7.1).
    """
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": PRIMARY_PASSWORD},
    )
    assert resp.status_code == status.HTTP_200_OK, (
        f"primary login -> {resp.status_code}: {resp.text[:200]}"
    )
    body = resp.json()
    # No session token at the primary step for a 2FA-enabled user.
    assert body.get("requires_2fa") is True
    assert "access_token" not in body
    assert "totp" in body.get("methods", [])
    return body["challenge_token"]


# TOTP secrets are generated exactly as the app does (pyotp base32 secrets).
_secret = st.builds(lambda _: pyotp.random_base32(), st.integers())

# Candidate "invalid" codes: 6-digit strings plus a few odd shapes. Any that
# happen to verify for the secret are filtered out below so the invalid branch
# is genuinely invalid.
_code_candidate = st.one_of(
    st.text(alphabet="0123456789", min_size=6, max_size=6),
    st.text(alphabet="0123456789", min_size=1, max_size=8),
    st.just("000000"),
)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(secret=_secret)
def test_valid_totp_code_issues_session_token(client, db_session, secret):
    """A code valid for the user's secret issues a session token.

    Validates: Requirements 7.1
    """
    user = _make_totp_user(db_session, secret)
    user_id = user.id
    try:
        challenge_token = _login_get_challenge(client, user.email)
        valid_code = pyotp.TOTP(secret).now()

        resp = client.post(
            "/api/auth/login/2fa",
            json={"challenge_token": challenge_token, "code": valid_code},
        )

        assert resp.status_code == status.HTTP_200_OK, (
            f"login/2fa with valid code -> {resp.status_code}: {resp.text[:200]}"
        )
        body = resp.json()
        # A valid code MUST yield a usable session token (Req 7.1).
        assert body.get("access_token"), "valid TOTP code must issue a token"
        assert body.get("token_type") == "bearer"
    finally:
        _cleanup_user(db_session, user_id)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(secret=_secret, candidate=_code_candidate)
def test_invalid_totp_code_is_rejected_and_issues_no_token(
    client, db_session, secret, candidate
):
    """A code not valid for the user's secret is rejected with no token.

    Validates: Requirements 7.3
    """
    # Guard: ensure the candidate is genuinely invalid for this secret within
    # the same +/-1 window the endpoint uses. If it happens to be valid, skip
    # (the valid branch is covered by the other property).
    if totp.verify_code(secret, candidate):
        return

    user = _make_totp_user(db_session, secret)
    user_id = user.id
    try:
        challenge_token = _login_get_challenge(client, user.email)

        resp = client.post(
            "/api/auth/login/2fa",
            json={"challenge_token": challenge_token, "code": candidate},
        )

        # An invalid code must NOT succeed and must NOT return a session token
        # (Requirement 7.3).
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED, (
            f"invalid code {candidate!r} -> {resp.status_code}: {resp.text[:200]}"
        )
        body = resp.json()
        assert "access_token" not in body, (
            f"invalid code {candidate!r} must not issue a token"
        )
        # The endpoint reports a verification error for invalid 2FA codes. The
        # global handler wraps ``ErrorResponse.create`` output under ``error``.
        error = body.get("error", {})
        code = error.get("code") if isinstance(error, dict) else None
        assert code == "INVALID_2FA_CODE", (
            f"expected INVALID_2FA_CODE for {candidate!r}, got {body!r}"
        )
    finally:
        _cleanup_user(db_session, user_id)

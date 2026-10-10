"""Property-based test for the TOTP confirmation guard (task 3.4).

Feature spec: .kiro/specs/account-security

Property 2: TOTP confirmation guard

For any generated TOTP secret, submitting a code that is valid for that secret
enables TOTP and persists the secret, while submitting any code that is not
valid for that secret is rejected and leaves TOTP disabled.

Feature: account-security, Property 2: TOTP confirmation guard

Validates: Requirements 5.3, 5.4, 5.5

State isolation note: the conftest ``client`` fixture is function-scoped and
recreates the DB per test, but ``@given`` runs many examples inside a SINGLE
test function (one DB). Each example is therefore self-isolating: it creates a
fresh user (unique email) with a pending TOTP secret, drives the confirm
endpoint, asserts, then deletes the user it created so state never leaks
between examples. Function-scoped-fixture health checks are suppressed as
recommended by Hypothesis for this pattern.
"""
import uuid

import pyotp
import pytest
from fastapi import status
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.auth import totp
from app.auth.token import create_access_token
from app.models import User, UserRole


def _headers(user):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _session():
    """Open a session on the same engine the conftest test harness uses."""
    from tests.conftest import TestingSessionLocal
    return TestingSessionLocal()


def _make_user_with_pending_secret(secret: str):
    """Create a fresh user (unique email) holding a pending TOTP secret.

    Mirrors the state produced by ``POST /2fa/totp/setup``: ``totp_secret`` is
    set while ``totp_enabled`` stays false.
    """
    db = _session()
    try:
        user = User(
            email=f"totp-{uuid.uuid4().hex}@security.test",
            password_hash="hashed_password",
            first_name="Totp",
            last_name="User",
            role=UserRole.MEMBER,
            is_email_verified=True,
            totp_secret=secret,
            totp_enabled=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _delete_user(user_id):
    db = _session()
    try:
        db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _reload(user_id):
    """Return the fresh persisted TOTP state for a user."""
    db = _session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        return user.totp_enabled, user.totp_secret
    finally:
        db.close()


# TOTP secrets are generated exactly as the app does (pyotp base32 secrets).
_secret = st.builds(lambda _: pyotp.random_base32(), st.integers())

# Candidate "invalid" codes: 6-digit strings plus a few odd shapes. We filter
# out any candidate that actually verifies for the secret (accounting for the
# +/-1 window used by verify_code) so the invalid branch is genuinely invalid.
_code_candidate = st.one_of(
    st.text(alphabet="0123456789", min_size=6, max_size=6),
    st.text(alphabet="0123456789", min_size=1, max_size=8),
    st.just(""),
    st.just("000000"),
)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(secret=_secret)
def test_valid_totp_code_enables_and_persists(client, secret):
    """A code valid for the pending secret enables TOTP and keeps the secret.

    Validates: Requirements 5.3, 5.4
    """
    user = _make_user_with_pending_secret(secret)
    try:
        valid_code = pyotp.TOTP(secret).now()

        resp = client.post(
            "/api/auth/2fa/totp/confirm",
            json={"code": valid_code},
            headers=_headers(user),
        )

        assert resp.status_code == status.HTTP_200_OK, (
            f"confirm with valid code -> {resp.status_code}: {resp.text[:200]}"
        )
        assert resp.json() == {"totp_enabled": True}

        enabled, stored_secret = _reload(user.id)
        assert enabled is True, "valid code must enable TOTP (Req 5.4)"
        assert stored_secret == secret, "secret must persist unchanged (Req 5.4)"
    finally:
        _delete_user(user.id)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(secret=_secret, candidate=_code_candidate)
def test_invalid_totp_code_is_rejected_and_leaves_disabled(client, secret, candidate):
    """A code not valid for the secret is rejected and leaves TOTP disabled.

    Validates: Requirements 5.3, 5.5
    """
    # Guard: ensure the candidate is genuinely invalid for this secret within
    # the same +/-1 window the endpoint uses. If it happens to be valid, skip
    # (the valid branch is covered by the other property).
    if totp.verify_code(secret, candidate):
        return

    user = _make_user_with_pending_secret(secret)
    try:
        resp = client.post(
            "/api/auth/2fa/totp/confirm",
            json={"code": candidate},
            headers=_headers(user),
        )

        # Empty/short codes may be rejected by request validation (422); any
        # non-empty invalid code hits the guard and returns 400 INVALID_2FA_CODE.
        # In every case the request must NOT succeed and TOTP must stay disabled.
        assert resp.status_code != status.HTTP_200_OK, (
            f"invalid code {candidate!r} must not succeed, got 200"
        )
        assert resp.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ), f"unexpected status for invalid code {candidate!r}: {resp.status_code}"

        enabled, _ = _reload(user.id)
        assert enabled is False, (
            f"invalid code {candidate!r} must leave TOTP disabled (Req 5.5)"
        )
    finally:
        _delete_user(user.id)

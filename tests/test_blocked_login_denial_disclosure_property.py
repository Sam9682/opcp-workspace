"""Property test for non-disclosure of the blocked-login denial response.

Feature: expired-user-login-block
Task 2.2 - Write property test for non-disclosure of the raised response.

Property 5: Blocked-denial response discloses no account state

For any blocked user on either path, the body of the raised 401 response SHALL
exclude the user's membership_status value, email address, and account
identifier, and SHALL be indistinguishable from the generic
invalid-credentials response.

Validates: Requirements 3.3

This exercises ``app.auth.router._deny_blocked_login`` directly across many
generated blocked identities. The routine persists an AuditLog (server-side,
captured here by a fake session) and raises an HTTPException; the property
inspects the *raised response body* only. Account-identifying values live in
the persisted AuditLog (not returned to the caller), so they must never appear
in the raised HTTPException detail.
"""
import json
import uuid

import pytest
from fastapi import HTTPException, status
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth.router import _deny_blocked_login, BLOCKED_MEMBERSHIP_STATUSES


class _FakeSession:
    """Minimal stand-in for a SQLAlchemy session.

    Captures ``add`` / ``commit`` calls so the denial routine's audit
    persistence succeeds without a real database. The persisted record is NOT
    the subject under test here (Property 5 is about the *raised response*),
    but we keep it to confirm account state lands server-side rather than in
    the caller-facing body.
    """

    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True


class _FakeUser:
    """Lightweight user carrying only the fields the routine reads."""

    def __init__(self, user_id, email, membership_status):
        self.id = user_id
        self.email = email
        self.membership_status = membership_status


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    """Minimal Request stand-in supporting ``headers`` and ``client``.

    ``_client_info`` reads ``headers.get("x-forwarded-for")``,
    ``headers.get("user-agent")`` and ``request.client.host``.
    """

    def __init__(self):
        self.headers = {}
        self.client = _FakeClient("127.0.0.1")


# Blocked identities: varied email / id / status drawn from the blocked set.
_emails = st.emails()
_ids = st.uuids()
_blocked_statuses = st.sampled_from(sorted(BLOCKED_MEMBERSHIP_STATUSES))
_audit_actions = st.sampled_from(["LOGIN_FAILED", "LOGIN_2FA_FAILED"])


def _body_text(body) -> str:
    """Flatten the error body into a single lowercase string for substring checks."""
    return json.dumps(body, default=str).lower()


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(
    user_id=_ids,
    email=_emails,
    membership_status=_blocked_statuses,
    audit_action=_audit_actions,
)
def test_blocked_denial_response_discloses_no_account_state(
    user_id, email, membership_status, audit_action
):
    """Feature: expired-user-login-block, Property 5: Blocked-denial response
    discloses no account state.

    The raised HTTPException carries only INVALID_CREDENTIALS with empty details
    and excludes membership_status, email, and account id. Validates Req 3.3.
    """
    user = _FakeUser(user_id=user_id, email=email, membership_status=membership_status)
    db = _FakeSession()
    request = _FakeRequest()

    with pytest.raises(HTTPException) as exc_info:
        _deny_blocked_login(db, user, request, audit_action)

    exc = exc_info.value

    # Generic 401, indistinguishable from a wrong-password failure.
    assert exc.status_code == status.HTTP_401_UNAUTHORIZED

    body = exc.detail
    error = body["error"]

    # Only the generic code and message; details is empty.
    assert error["code"] == "INVALID_CREDENTIALS"
    assert error["message"] == "Invalid email or password"
    assert error["details"] == {}

    # The caller-facing body must not surface any account-state keys.
    assert "membership_status" not in error
    assert "membership_status" not in error["details"]
    assert "email" not in error["details"]
    assert "reason" not in error["details"]

    # No account-identifying value appears anywhere in the serialized body.
    flat = _body_text(body)
    assert email.lower() not in flat
    assert str(user_id).lower() not in flat
    assert membership_status.lower() not in flat

    # Server-side audit still captured the account state (persisted, not returned).
    assert db.committed is True
    assert len(db.added) == 1
    audit = db.added[0]
    assert audit.action == audit_action
    assert audit.details["email"] == email
    assert audit.details["reason"] == "membership_blocked"

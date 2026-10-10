"""Preservation property tests for the event-creation bugfix.

Spec: .kiro/specs/event-creation-failure/

Property 2 (Preservation): for any input where the bug condition does NOT hold
(isBugCondition returns false), the fixed code SHALL produce the same result as
the original code.

Methodology: OBSERVATION-FIRST. These assertions were written after running the
UNFIXED code and recording its actual outputs; they MUST PASS on the unfixed
code, establishing the baseline behavior the fix must preserve.

Observed baseline (unfixed code, run 2026-09-28):
  Schema level (EventCreateRequest instantiated directly):
    - aware future well-ordered (end > start): accepted; tzinfo preserved.
    - naive far-future well-ordered (both far in the future so the naive
      local-clock future check passes): accepted; tzinfo stays None.
    - assigned_user_ids default = None; assigned_user_id default = None.
  HTTP level (via TestClient + conftest fixtures):
    - valid create with assignee => 201; assigned_user_ids persisted and the
      first assignee mirrored into the deprecated assigned_user_id (Req 3.1, 3.2).
    - omitted assigned_user_ids => 201, assigned_user_ids == [] (public) (Req 3.3).
    - non-existent assignee => 400, body error.code == INVALID_ASSIGNED_USER,
      and no event created (Req 3.4).
    - non-admin create => 403, body error.code == INSUFFICIENT_PERMISSIONS (Req 3.5).
    - listing events => 200 (Req 3.6).

NOTE on status codes: a validation_exception_handler registered in
app.error_handlers maps Pydantic RequestValidationError to HTTP 400 (not 422),
returning {"error": {"code": "VALIDATION_ERROR", ...}}. Preservation assertions
below reflect that ACTUAL behavior rather than the raw FastAPI 422.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6

These tests are pure preservation and MUST pass both before and after the fix.
"""
import uuid
import unittest.mock as m
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from pydantic import ValidationError

from app.models import User, UserRole, Event, EventAssignment, EventStatus
from app.auth.password import hash_password
from app.auth.token import create_access_token
from app.events.schemas import EventCreateRequest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _mk_user(db_session, email, role=UserRole.MEMBER):
    user = User(
        email=email,
        password_hash=hash_password("SecurePass123"),
        first_name=email.split("@")[0],
        last_name="User",
        role=role,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest.fixture
def admin(db_session):
    return _mk_user(db_session, "admin@example.com", UserRole.ADMINISTRATOR)


@pytest.fixture
def alice(db_session):
    return _mk_user(db_session, "alice@example.com")


@pytest.fixture
def bob(db_session):
    return _mk_user(db_session, "bob@example.com")


@pytest.fixture
def member(db_session):
    return _mk_user(db_session, "member@example.com")


def _iso_future(days, hours=0, minutes=0):
    return (
        datetime.now(timezone.utc)
        + timedelta(days=days, hours=hours, minutes=minutes)
    ).isoformat()


# ===========================================================================
# Schema-level preservation (no HTTP): non-bug-condition date pairs accepted.
#
# Bug condition: equal dates OR naive dates rejected by the naive local-clock
# comparison. Non-bug inputs (end strictly > start AND genuinely, clearly in
# the future) must continue to be ACCEPTED. Observed baseline: accepted, tzinfo
# preserved as-is (aware stays aware, naive stays naive).
# ===========================================================================

@pytest.mark.property
@settings(max_examples=40, deadline=None)
@given(
    start_days=st.integers(min_value=2, max_value=3650),
    duration_minutes=st.integers(min_value=1, max_value=60 * 24 * 30),
)
def test_aware_well_ordered_future_is_accepted(start_days, duration_minutes):
    """Aware, clearly-future, strictly-ordered dates accepted (Req 3.1).

    These are NOT bug-condition inputs (aware, end > start, clearly future), so
    the observed baseline is acceptance with tzinfo preserved.
    """
    start = datetime.now(timezone.utc) + timedelta(days=start_days)
    end = start + timedelta(minutes=duration_minutes)

    req = EventCreateRequest(title="t", start_date=start, end_date=end)

    assert req.start_date is not None
    assert req.end_date is not None
    # Baseline: aware input keeps its tzinfo; end strictly after start.
    assert req.start_date.tzinfo is not None
    assert req.end_date > req.start_date


@pytest.mark.property
@settings(max_examples=40, deadline=None)
@given(
    start_days=st.integers(min_value=2, max_value=3650),
    duration_minutes=st.integers(min_value=1, max_value=60 * 24 * 30),
)
def test_naive_far_future_well_ordered_is_accepted(start_days, duration_minutes):
    """Naive, clearly-future (>= 2 days out), strictly-ordered dates accepted.

    A naive date at least two days in the future passes the naive local-clock
    future check regardless of server offset, so this is the preservation
    baseline (NOT the near-future naive bug condition). Observed baseline:
    accepted, tzinfo stays None (Req 3.1, 3.6).
    """
    naive_now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = naive_now + timedelta(days=start_days)
    end = start + timedelta(minutes=duration_minutes)

    req = EventCreateRequest(title="t", start_date=start, end_date=end)

    assert req.start_date.tzinfo is None
    assert req.end_date > req.start_date


def test_default_assignment_fields_are_none():
    """Omitted assignment fields default to None on the schema (Req 3.2, 3.3)."""
    start = datetime.now(timezone.utc) + timedelta(days=3)
    req = EventCreateRequest(title="t", start_date=start, end_date=start + timedelta(hours=1))
    assert req.assigned_user_ids is None
    assert req.assigned_user_id is None


# ===========================================================================
# HTTP-level preservation via the create endpoint.
# ===========================================================================

@pytest.mark.property
@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    start_days=st.integers(min_value=2, max_value=365),
    duration_hours=st.integers(min_value=1, max_value=72),
    n_assignees=st.integers(min_value=0, max_value=2),
)
def test_valid_creation_and_assignment_preserved(
    client, db_session, admin, alice, bob, start_days, duration_hours, n_assignees
):
    """Valid create: 201, assignees persisted, first mirrored (Req 3.1, 3.2, 3.3).

    Property over random future well-ordered date pairs and random assignment
    sets (0, 1 or 2 known users). Observed baseline:
      - 201 Created,
      - returned assigned_user_ids equals the requested set,
      - assigned_user_id mirrors the first assignee (or None when public),
      - empty/omitted assignees => public (assigned_user_ids == []).
    """
    candidates = [alice, bob]
    assignees = candidates[:n_assignees]
    payload = {
        "title": "Preserved valid",
        "description": "d",
        "start_date": _iso_future(start_days),
        "end_date": _iso_future(start_days, hours=duration_hours),
        "location": "HQ",
    }
    if assignees:
        payload["assigned_user_ids"] = [str(u.id) for u in assignees]

    with m.patch("app.events.router.email_service.send_email", return_value=True):
        resp = client.post("/api/events", json=payload, headers=_headers(admin))

    assert resp.status_code == 201, resp.text
    event = resp.json()["event"]
    assert set(event["assigned_user_ids"]) == {str(u.id) for u in assignees}
    if assignees:
        # First assignee mirrored into the deprecated single-value field.
        assert event["assigned_user_id"] == str(assignees[0].id)
    else:
        # Empty/omitted assignees => public event.
        assert event["assigned_user_ids"] == []
        assert event["assigned_user_id"] is None
    assert event["status"] == "scheduled"


def test_public_event_when_assignees_omitted(client, admin):
    """Omitted assigned_user_ids => public event, 201 (Req 3.3)."""
    payload = {
        "title": "Public",
        "start_date": _iso_future(5),
        "end_date": _iso_future(6),
    }
    with m.patch("app.events.router.email_service.send_email", return_value=True):
        resp = client.post("/api/events", json=payload, headers=_headers(admin))
    assert resp.status_code == 201, resp.text
    assert resp.json()["event"]["assigned_user_ids"] == []


def test_invalid_assigned_user_rejected_and_no_event(client, db_session, admin):
    """Non-existent assignee => 400 INVALID_ASSIGNED_USER, no event (Req 3.4)."""
    before = db_session.query(Event).count()
    bogus = str(uuid.uuid4())
    payload = {
        "title": "Bad assignee",
        "start_date": _iso_future(5),
        "end_date": _iso_future(6),
        "assigned_user_ids": [bogus],
    }
    resp = client.post("/api/events", json=payload, headers=_headers(admin))

    # Observed baseline: HTTP 400 with error.code INVALID_ASSIGNED_USER.
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "INVALID_ASSIGNED_USER"
    # No event created.
    assert db_session.query(Event).count() == before


@pytest.mark.property
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(n_assignees=st.integers(min_value=0, max_value=2))
def test_non_admin_create_forbidden(client, db_session, admin, alice, member, n_assignees):
    """Non-admin create => 403 INSUFFICIENT_PERMISSIONS (Req 3.5).

    Authorization is enforced regardless of the (otherwise-valid) payload shape.
    """
    candidates = [alice, admin]
    payload = {
        "title": "X",
        "start_date": _iso_future(5),
        "end_date": _iso_future(6),
    }
    if n_assignees:
        payload["assigned_user_ids"] = [str(u.id) for u in candidates[:n_assignees]]

    resp = client.post("/api/events", json=payload, headers=_headers(member))

    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_listing_events_unchanged(client, admin):
    """Listing events => 200 (Req 3.6)."""
    resp = client.get("/api/events", headers=_headers(admin))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert "events" in body and "total" in body

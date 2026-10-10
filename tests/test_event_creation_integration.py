"""Integration tests for the full event-creation flow (fixed code).

Spec: .kiro/specs/event-creation-failure/ (Task 4)

These integration tests exercise the end-to-end create flow via the API against
the FIXED code and are expected to PASS. They complement the exploration
(Task 1) and preservation (Task 2) tests by asserting the full-stack contract:

- Equal start/end dates => a deterministic validation-failure response that
  carries the specific "End date must be after start date." message AND a
  server-side WARNING log entry (no silent failure).
- Genuinely-future, well-ordered, timezone-naive dates => HTTP 201 and the
  created event appears in the subsequent list.

NOTE on the response contract: the app registers a `validation_exception_handler`
(app.error_handlers) that maps Pydantic RequestValidationError to HTTP 400 with
body {"error": {"code": "VALIDATION_ERROR", "details": {"errors": [...]}}} --
NOT a raw 422. These tests assert against that ACTUAL contract.

The WARNING log entry is emitted by the same handler through the shared logger
in app.logging_config; we capture it via caplog on that logger's name ("OPCP").

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 3.1, 3.6
"""
import logging
import unittest.mock as m
from datetime import datetime, timedelta, timezone

import pytest

from app.models import User, UserRole, Event
from app.auth.password import hash_password
from app.auth.token import create_access_token


# ---------------------------------------------------------------------------
# Helpers / fixtures (mirrors tests/test_event_creation_preservation.py)
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


def _naive_future_iso(days, hours=0, minutes=0):
    """A timezone-naive (no offset) ISO string a given amount into the future.

    This mirrors what the browser's `datetime-local` input produces: a wall-clock
    value with no timezone suffix. Well clear of "now" so the future check passes.
    """
    dt = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        + timedelta(days=days, hours=hours, minutes=minutes)
    )
    # No tzinfo -> isoformat() emits e.g. "2026-09-28T17:56:00" (naive).
    return dt.isoformat()


# ===========================================================================
# Bug-condition path: equal dates => clear, specific message + server log.
# ===========================================================================

def test_equal_dates_return_specific_validation_error(client, admin):
    """Equal start/end dates yield a 400 VALIDATION_ERROR whose details carry
    the specific "End date must be after start date." message (Req 2.1, 2.3).
    """
    same = _naive_future_iso(days=30)
    payload = {
        "title": "test",
        "description": "test",
        "start_date": same,
        "end_date": same,
        "location": "test",
        "max_participants": 1,
    }

    resp = client.post("/api/events", json=payload, headers=_headers(admin))

    # Actual contract: the validation_exception_handler maps the Pydantic error
    # to HTTP 400 with a VALIDATION_ERROR code (not a raw 422).
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"

    errors = body["error"]["details"]["errors"]
    messages = " ".join(e["message"] for e in errors)
    # The specific, actionable message reaches the client instead of a generic
    # opaque failure.
    assert "End date must be after start date." in messages
    # And it names the offending field.
    assert any(e["field"].endswith("end_date") for e in errors)


def test_equal_dates_emit_warning_log_and_create_no_event(client, admin, db_session, caplog):
    """The equal-dates validation failure is logged at WARNING (diagnosable,
    never silent) and no event is created (Req 2.2, 2.1)."""
    before = db_session.query(Event).count()
    same = _naive_future_iso(days=30)
    payload = {
        "title": "test",
        "description": "test",
        "start_date": same,
        "end_date": same,
        "location": "test",
        "max_participants": 1,
    }

    # Capture WARNING records from the application logger used by the handler.
    with caplog.at_level(logging.WARNING, logger="OPCP"):
        resp = client.post("/api/events", json=payload, headers=_headers(admin))

    assert resp.status_code == 400, resp.text

    warnings = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "Validation error" in r.getMessage()
    ]
    assert warnings, "expected a WARNING log entry recording the validation failure"
    logged = " ".join(r.getMessage() for r in warnings)
    # The log line records the route and the specific field/message so the
    # failure is diagnosable server-side.
    assert "/api/events" in logged
    assert "End date must be after start date." in logged

    # No event was persisted by the failed submission.
    assert db_session.query(Event).count() == before


# ===========================================================================
# Fixed-behavior path: genuinely-future well-ordered NAIVE dates => 201 + listed.
# ===========================================================================

def test_naive_future_well_ordered_dates_create_and_list(client, admin):
    """Timezone-naive, clearly-future, well-ordered dates => HTTP 201 and the
    created event appears in the subsequent list (Req 2.4, 3.1, 3.6)."""
    payload = {
        "title": "Naive future event",
        "description": "created from datetime-local style naive values",
        "start_date": _naive_future_iso(days=10),
        "end_date": _naive_future_iso(days=10, hours=2),
        "location": "HQ",
        "max_participants": 5,
    }

    with m.patch("app.events.router.email_service.send_email", return_value=True):
        resp = client.post("/api/events", json=payload, headers=_headers(admin))

    assert resp.status_code == 201, resp.text
    created = resp.json()["event"]
    assert created["title"] == "Naive future event"
    assert created["status"] == "scheduled"

    # The event appears in the subsequent list.
    list_resp = client.get("/api/events", headers=_headers(admin))
    assert list_resp.status_code == 200, list_resp.text
    listed = list_resp.json()["events"]
    ids = {e["id"] for e in listed}
    assert created["id"] in ids
    titles = {e["title"] for e in listed}
    assert "Naive future event" in titles

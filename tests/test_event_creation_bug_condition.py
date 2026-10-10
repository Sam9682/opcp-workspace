"""Bug condition exploration tests for event creation failure.

Spec: .kiro/specs/event-creation-failure/

These tests encode the EXPECTED (fixed) behavior for the event-creation bug
condition. They are written BEFORE the fix and are EXPECTED TO FAIL on the
unfixed code -- their failure confirms the bug exists.

Bug condition (isBugCondition):
  - equal start_date/end_date, OR
  - timezone-naive start_date/end_date rejected only because
    validate_start_date compares against a naive local-clock now
    (datetime.now(v.tzinfo) where tzinfo is None).

Property 1 (Bug Condition): the system SHALL respond deterministically -- either
create the event when the dates are genuinely valid/well-ordered under an
unambiguous time reference, or return a clear, specific message that names the
offending date rule (e.g. mentions that end must be after start), never an
opaque/generic message.

Validates: Requirements 1.1, 1.2, 1.3, 1.4 (2.1, 2.2, 2.3, 2.4 after fix)

DO NOT "fix" these tests when they fail on unfixed code -- the failure IS the
expected outcome and documents the bug.
"""
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from app.events.schemas import EventCreateRequest


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_request(start_date, end_date):
    """Instantiate EventCreateRequest directly (no HTTP layer)."""
    return EventCreateRequest(
        title="test",
        description="test",
        start_date=start_date,
        end_date=end_date,
        location="test",
        max_participants=1,
    )


def _all_error_messages(exc_info) -> str:
    """Concatenate all pydantic error messages, lowercased, for inspection."""
    return " ".join(err.get("msg", "") for err in exc_info.value.errors()).lower()


def _mentions_end_after_start(message: str) -> bool:
    """A clear, specific message must name BOTH the end and start date rule."""
    msg = message.lower()
    return "end" in msg and "start" in msg and "after" in msg


# --------------------------------------------------------------------------
# Bug condition 1: equal start/end dates at a far-future instant.
#
# Expected (fixed) behavior: equal dates are disallowed, but the validation
# message SHALL be clear and specific -- it must name the end/start "after"
# rule rather than an opaque generic message.
#
# On UNFIXED code the message is "end_date must be after start_date" (uses the
# raw field names, not a user-clear phrasing). We assert the fixed, clear
# phrasing to make this test fail on unfixed code as intended.
# --------------------------------------------------------------------------

def test_equal_dates_far_future_yields_clear_specific_message():
    """Equal dates (both 2030-01-01T10:00) must yield a clear, specific message."""
    both = datetime(2030, 1, 1, 10, 0)  # timezone-naive, far future

    with pytest.raises(ValidationError) as exc_info:
        _make_request(both, both)

    messages = _all_error_messages(exc_info)
    # EXPECTED-ON-FIX assertion: a clear, actionable message that names the rule.
    # On unfixed code the message reads "end_date must be after start_date"
    # (raw field-name phrasing considered opaque/generic for the user), so this
    # assertion FAILS -> confirms the bug.
    assert "end date must be after start date" in messages, (
        "Expected a clear, specific message naming the end/start-date rule; "
        f"got: {messages!r}"
    )


# --------------------------------------------------------------------------
# Bug condition 2: naive near-future start rejected by the naive local-clock
# comparison. A genuinely-future, well-ordered naive submission SHOULD be
# accepted under an unambiguous (UTC) time reference.
#
# We generate naive future date pairs a few minutes ahead of UTC wall-clock.
# On UNFIXED code, validate_start_date compares against datetime.now(None)
# (server LOCAL clock). For any server whose local offset is ahead of UTC
# (e.g. UTC+X), a start only a few minutes ahead of UTC "now" is BEHIND the
# server's local "now" and is rejected as "not in the future".
# --------------------------------------------------------------------------

@settings(max_examples=25, deadline=None)
@given(offset_minutes=st.integers(min_value=1, max_value=59))
def test_naive_near_future_start_is_accepted(offset_minutes):
    """A genuinely-future, well-ordered naive submission must be accepted.

    start_date = UTC now + offset_minutes (naive), end_date = start + 1h.
    Under an unambiguous time reference this is clearly future and well
    ordered, so it SHALL be accepted (no ValidationError).
    """
    now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    start = now_utc_naive + timedelta(minutes=offset_minutes)
    end = start + timedelta(hours=1)

    # EXPECTED-ON-FIX: no exception. On unfixed code, when the server local
    # clock is ahead of UTC this raises "start_date must be in the future",
    # confirming the naive local-clock dependency bug.
    try:
        req = _make_request(start, end)
    except ValidationError as exc:  # pragma: no cover - documents the bug
        pytest.fail(
            "Genuinely-future, well-ordered naive dates were rejected "
            f"(offset={offset_minutes}m): {_all_error_messages_from_exc(exc)!r}"
        )
    assert req.start_date is not None
    assert req.end_date is not None


def _all_error_messages_from_exc(exc: ValidationError) -> str:
    return " ".join(err.get("msg", "") for err in exc.errors()).lower()

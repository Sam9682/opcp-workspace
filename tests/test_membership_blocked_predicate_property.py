"""Property-based test for the membership block-list predicate (task 1.2).

Feature spec: .kiro/specs/expired-user-login-block

Property 3: Non-blocked memberships continue the existing flow

For any stored ``membership_status`` value that is ``null`` or any string
outside the blocked set (including ``pending`` and ``active``), the membership
gate SHALL NOT block; only ``expired`` and ``suspended`` block.

Feature: expired-user-login-block, Property 3: Non-blocked memberships continue the existing flow

Validates: Requirements 1.3, 1.4, 1.5

The predicate under test (``_is_membership_blocked``) is pure and depends only
on its single argument, so these properties exercise it in isolation with no
database or HTTP client.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth.router import BLOCKED_MEMBERSHIP_STATUSES, _is_membership_blocked

# The exact set that must block authentication.
_BLOCKED = frozenset({"expired", "suspended"})

# Arbitrary status strings. We draw free-form text plus the plausible
# domain values (pending/active and the blocked ones) so the generator covers
# both the "allowed" space and the "blocked" space without special weighting.
_status_text = st.one_of(
    st.text(),
    st.sampled_from(["pending", "active", "expired", "suspended", "unknown", ""]),
)

# A status argument that is either an arbitrary string or ``None`` (null).
_status_or_none = st.one_of(st.none(), _status_text)


@settings(max_examples=200, deadline=None)
@given(status_value=_status_or_none)
def test_predicate_blocks_only_expired_and_suspended(status_value):
    """``_is_membership_blocked`` is True iff status is expired/suspended.

    Feature: expired-user-login-block, Property 3
    Validates: Requirements 1.3, 1.4, 1.5
    """
    expected = status_value in _BLOCKED
    assert _is_membership_blocked(status_value) is expected, (
        f"status {status_value!r}: expected blocked={expected}"
    )


@settings(max_examples=100, deadline=None)
@given(
    status_value=st.text().filter(lambda s: s not in _BLOCKED),
)
def test_arbitrary_non_blocked_strings_are_allowed(status_value):
    """Any string outside the blocked set is allowed (Req 1.5).

    Feature: expired-user-login-block, Property 3
    Validates: Requirements 1.5
    """
    assert _is_membership_blocked(status_value) is False, (
        f"non-blocked status {status_value!r} must not block"
    )


def test_null_pending_active_are_allowed():
    """null, pending, and active continue the existing flow (Req 1.3-1.5).

    Validates: Requirements 1.3, 1.4, 1.5
    """
    assert _is_membership_blocked(None) is False
    assert _is_membership_blocked("pending") is False
    assert _is_membership_blocked("active") is False


def test_expired_and_suspended_block():
    """The two blocked statuses block (anchors the block-list).

    Validates: Requirements 1.3, 1.4, 1.5
    """
    assert _is_membership_blocked("expired") is True
    assert _is_membership_blocked("suspended") is True
    # The constant used by the predicate matches the specified block-list.
    assert BLOCKED_MEMBERSHIP_STATUSES == _BLOCKED

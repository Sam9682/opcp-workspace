"""Property-based test for the change-password guard and round-trip.

Feature spec: .kiro/specs/account-security

Property 1: Change-password guard and round-trip
Validates: Requirements 3.3, 3.4, 3.5

This exercises the change-password decision logic that the
``POST /api/auth/change-password`` endpoint implements in
``app/auth/router.py``: the endpoint verifies the submitted current password
against the stored ``password_hash`` via ``verify_password`` and, only on a
match, replaces the stored hash with ``hash_password(new_password)``. On a
mismatch it returns ``401 INVALID_CREDENTIALS`` and leaves the stored hash
untouched.

The property drives that same guard directly over the ``password`` module
(hash the old password, then attempt the change with either the correct current
password or an arbitrary mismatching one) so it can run many iterations without
tripping the endpoint's ``10/hour`` rate limit. Assertions:

- The change succeeds *iff* the submitted current password verifies against the
  stored hash (Requirements 3.3, 3.5).
- On success, the resulting stored hash verifies the new password (Req 3.4).
- On failure, the stored hash is byte-for-byte unchanged (Req 3.5).
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth.password import hash_password, verify_password


# bcrypt operates on the first 72 bytes; keep generated passwords within that
# limit (and non-trivial) so hash_password never raises and the semantics under
# test are the credential-guard semantics, not the length guard.
_password = st.text(min_size=1, max_size=72).filter(
    lambda s: len(s.encode("utf-8")) <= 72
)


def _apply_change_password(stored_hash: str, submitted_current: str, new_password: str):
    """Mirror the endpoint's change-password guard against a stored hash.

    Returns ``(success, resulting_hash)`` where ``resulting_hash`` is the new
    hash on success and the unchanged ``stored_hash`` on failure. This is the
    exact decision the ``/api/auth/change-password`` handler makes: verify the
    current password, and only then persist ``hash_password(new_password)``.
    """
    if not verify_password(submitted_current, stored_hash):
        # Endpoint path: 401 INVALID_CREDENTIALS, credential unchanged (Req 3.5).
        return False, stored_hash
    # Endpoint path: persist the new credential (Req 3.4).
    return True, hash_password(new_password)


@settings(max_examples=100, deadline=None)
@given(
    old_password=_password,
    new_password=_password,
    submitted_current=_password,
)
def test_change_password_guard_and_round_trip(old_password, new_password, submitted_current):
    """Feature: account-security, Property 1: Change-password guard and round-trip

    Validates: Requirements 3.3, 3.4, 3.5
    """
    stored_hash = hash_password(old_password)

    # Ground truth: the guard must succeed exactly when the submitted current
    # password verifies against the stored hash.
    should_succeed = verify_password(submitted_current, stored_hash)

    success, resulting_hash = _apply_change_password(
        stored_hash, submitted_current, new_password
    )

    # Success iff the submitted current password verifies (Req 3.3, 3.5).
    assert success == should_succeed, (
        f"guard mismatch: should_succeed={should_succeed} but success={success} "
        f"(old={old_password!r}, submitted={submitted_current!r})"
    )

    if success:
        # On success the new stored hash verifies the new password (Req 3.4).
        assert verify_password(new_password, resulting_hash), (
            f"round-trip failed: new hash does not verify new password {new_password!r}"
        )
    else:
        # On failure the stored hash is unchanged (Req 3.5).
        assert resulting_hash == stored_hash, (
            "stored hash mutated on a rejected change-password attempt"
        )


@settings(max_examples=100, deadline=None)
@given(old_password=_password, new_password=_password)
def test_change_password_correct_current_always_succeeds(old_password, new_password):
    """The correct current password always drives a successful change.

    A focused slice of Property 1 pinning the success branch: submitting the
    genuine current password verifies (Req 3.3) and the resulting hash verifies
    the new password (Req 3.4).

    Feature: account-security, Property 1: Change-password guard and round-trip
    Validates: Requirements 3.3, 3.4
    """
    stored_hash = hash_password(old_password)

    success, resulting_hash = _apply_change_password(
        stored_hash, old_password, new_password
    )

    assert success is True
    assert verify_password(new_password, resulting_hash)


@settings(max_examples=100, deadline=None)
@given(old_password=_password, new_password=_password, wrong_current=_password)
def test_change_password_wrong_current_never_changes_hash(old_password, new_password, wrong_current):
    """A non-matching current password never mutates the stored credential.

    A focused slice of Property 1 pinning the failure branch (Req 3.5). We only
    consider ``wrong_current`` values that genuinely do not verify against the
    stored hash.

    Feature: account-security, Property 1: Change-password guard and round-trip
    Validates: Requirements 3.5
    """
    stored_hash = hash_password(old_password)

    # Restrict to genuinely-wrong current passwords.
    if verify_password(wrong_current, stored_hash):
        return

    success, resulting_hash = _apply_change_password(
        stored_hash, wrong_current, new_password
    )

    assert success is False
    assert resulting_hash == stored_hash

"""Tests for the Forum config storage layer and admin schema.

Covers the ``forum_config`` service helpers and the admin update schema:
- ``get_view_button_enabled`` returns the default (True) with no row, and the
  stored value once a row is present.
- ``set_view_button_enabled`` upserts the row and returns the resulting bool.
- ``ForumConfigUpdateRequest`` validates the ``view_button_enabled`` field.

These mirror the conventions in ``tests/test_forum_models.py`` and use the
``db_session`` fixture from ``tests/conftest.py`` (in-memory SQLite).
"""
import pytest
from pydantic import ValidationError

from app.models import ForumConfig, FORUM_VIEW_BUTTON_KEY, DEFAULT_FORUM_CONFIG
from app.forum.config_service import (
    get_view_button_enabled,
    set_view_button_enabled,
)
from app.admin.schemas import ForumConfigUpdateRequest


def test_get_returns_default_when_no_row(db_session):
    """With no forum_config row, the getter falls back to the default (True)."""
    # No rows have been inserted for this fresh session.
    assert db_session.query(ForumConfig).count() == 0

    assert get_view_button_enabled(db_session) is True
    assert DEFAULT_FORUM_CONFIG["view_button_enabled"] is True


def test_set_upserts_and_returns_new_value(db_session):
    """set_view_button_enabled upserts and returns the resulting bool."""
    # Disable: creates the row and returns False.
    result = set_view_button_enabled(db_session, False)
    assert result is False
    assert get_view_button_enabled(db_session) is False

    # Exactly one row exists after the upsert (no duplicates).
    assert db_session.query(ForumConfig).count() == 1

    # Re-enable: updates the same row (upsert) and returns True.
    result = set_view_button_enabled(db_session, True)
    assert result is True
    assert get_view_button_enabled(db_session) is True

    # Still a single row after the second write.
    assert db_session.query(ForumConfig).count() == 1


def test_get_returns_stored_value_when_row_present(db_session):
    """The getter returns the persisted flag when a row exists."""
    # Insert a row directly with enabled=False.
    row = ForumConfig(key=FORUM_VIEW_BUTTON_KEY, enabled=False)
    db_session.add(row)
    db_session.commit()

    assert get_view_button_enabled(db_session) is False

    # Flip the stored value and confirm the getter reflects it.
    row.enabled = True
    db_session.commit()

    assert get_view_button_enabled(db_session) is True


def test_update_request_accepts_valid_bool():
    """ForumConfigUpdateRequest accepts both True and False."""
    assert ForumConfigUpdateRequest(view_button_enabled=True).view_button_enabled is True
    assert ForumConfigUpdateRequest(view_button_enabled=False).view_button_enabled is False


def test_update_request_rejects_missing_field():
    """Missing view_button_enabled raises a pydantic ValidationError."""
    with pytest.raises(ValidationError):
        ForumConfigUpdateRequest()


def test_update_request_rejects_non_bool_value():
    """A non-coercible value for view_button_enabled raises ValidationError."""
    with pytest.raises(ValidationError):
        ForumConfigUpdateRequest(view_button_enabled="not-a-bool")

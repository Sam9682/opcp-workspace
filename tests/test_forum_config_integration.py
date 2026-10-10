"""Integration tests for the Forum config feature (Enhancement 2).

Exercises the public and admin HTTP surfaces end-to-end through the FastAPI
TestClient (in-memory SQLite from ``tests/conftest.py``):

- ``GET /api/forum/config`` (public, unauthenticated) returns the default
  ``{"view_button_enabled": true}`` and reflects updates made through the admin
  endpoint.
- ``GET`` / ``PUT /api/admin/forum-config`` require administrator access and
  round-trip the setting.
- Full flow: admin toggles the forum "View" button off then on; the public read
  endpoint (which the logged-out home page reads to decide whether to render the
  "View" button) tracks the change. AI provider toggles still work in the same
  session, independent of the forum setting.
- Backend ``/api/forum/topics/{id}/publichtml`` still serves its public HTML
  page unchanged.

Follows the admin-fixture pattern from ``tests/test_forum_moderation.py`` since
``conftest.py`` provides no administrator fixture. The member ``auth_headers``
fixture (a MEMBER token) from conftest is reused for the non-admin 403 checks.

Validates Requirements 2.3, 2.4, 3.3, 3.4, 3.5
"""

import pytest
from fastapi import status

from app.models import User, UserRole, Topic
from app.auth.token import create_access_token


@pytest.fixture
def administrator(db_session):
    """Create an administrator for admin-only endpoint tests."""
    user = User(
        email="admin@test.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(administrator):
    """Authorization headers carrying an administrator JWT."""
    token = create_access_token({"sub": str(administrator.id)})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Public read endpoint
# ---------------------------------------------------------------------------


def test_public_get_returns_default_true(client):
    """GET /api/forum/config (no auth) returns the default enabled flag.

    No forum_config row is seeded, so the service defaults to True.

    Validates Requirements 2.3, 2.4, 3.3
    """
    response = client.get("/api/forum/config")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"view_button_enabled": True}


# ---------------------------------------------------------------------------
# Admin GET authorization
# ---------------------------------------------------------------------------


def test_admin_get_requires_authentication(client):
    """GET /api/admin/forum-config without any credentials is rejected.

    HTTPBearer (auto_error=True) rejects the missing Authorization header with
    403 before the handler runs.

    Validates Requirement 2.3
    """
    response = client.get("/api/admin/forum-config")

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_get_forbidden_for_member(client, auth_headers):
    """A MEMBER token cannot read the admin forum config (403).

    Validates Requirement 2.3
    """
    response = client.get("/api/admin/forum-config", headers=auth_headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_get_ok_for_admin(client, admin_headers):
    """An administrator reads the default forum config.

    Validates Requirements 2.3, 3.3
    """
    response = client.get("/api/admin/forum-config", headers=admin_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"view_button_enabled": True}


# ---------------------------------------------------------------------------
# Admin PUT authorization + round-trip
# ---------------------------------------------------------------------------


def test_admin_put_forbidden_for_member(client, auth_headers):
    """A MEMBER token cannot update the forum config (403).

    Validates Requirement 2.4
    """
    response = client.put(
        "/api/admin/forum-config",
        json={"view_button_enabled": False},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_put_round_trip_and_public_reflects(client, admin_headers):
    """Admin PUT persists the flag; public GET reflects each change.

    Sets the flag False then True and confirms both the admin response and the
    public read endpoint track the stored value.

    Validates Requirements 2.3, 2.4, 3.3
    """
    # Disable via admin PUT.
    put_off = client.put(
        "/api/admin/forum-config",
        json={"view_button_enabled": False},
        headers=admin_headers,
    )
    assert put_off.status_code == status.HTTP_200_OK
    assert put_off.json() == {"view_button_enabled": False}

    # Admin GET reflects the disabled value.
    assert client.get(
        "/api/admin/forum-config", headers=admin_headers
    ).json() == {"view_button_enabled": False}

    # Public read reflects the disabled value.
    assert client.get("/api/forum/config").json() == {"view_button_enabled": False}

    # Re-enable via admin PUT.
    put_on = client.put(
        "/api/admin/forum-config",
        json={"view_button_enabled": True},
        headers=admin_headers,
    )
    assert put_on.status_code == status.HTTP_200_OK
    assert put_on.json() == {"view_button_enabled": True}

    # Public read reflects the re-enabled value.
    assert client.get("/api/forum/config").json() == {"view_button_enabled": True}


def test_public_read_reflects_admin_update(client, admin_headers):
    """After admin disables the flag, the public endpoint returns False.

    This is the exact signal the logged-out home page reads to decide whether to
    render the "View" button.

    Validates Requirements 2.4, 3.3
    """
    client.put(
        "/api/admin/forum-config",
        json={"view_button_enabled": False},
        headers=admin_headers,
    )

    response = client.get("/api/forum/config")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"view_button_enabled": False}


# ---------------------------------------------------------------------------
# Full flow: forum toggle + AI providers independent in the same session
# ---------------------------------------------------------------------------


def test_full_flow_forum_toggle_and_ai_providers_independent(client, admin_headers):
    """Toggling the forum "View" button does not disturb AI provider config.

    Full flow: admin disables the forum flag (logged-out home page would stop
    rendering the "View" button), then re-enables it (button restored). In the
    same session, AI provider GET/PUT keep working and round-trip independently
    of the forum setting; ``shai`` stays always-enabled.

    Validates Requirements 2.4, 3.3, 3.4
    """
    # Forum OFF -> public read reports False.
    client.put(
        "/api/admin/forum-config",
        json={"view_button_enabled": False},
        headers=admin_headers,
    )
    assert client.get("/api/forum/config").json() == {"view_button_enabled": False}

    # AI providers still work in the same session.
    providers_response = client.get("/api/admin/ai-providers", headers=admin_headers)
    assert providers_response.status_code == status.HTTP_200_OK
    providers = providers_response.json()["providers"]
    assert isinstance(providers, list)
    assert len(providers) > 0

    by_id = {p["provider"]: p for p in providers}
    # shai is always enabled and cannot be disabled.
    assert by_id["shai"]["enabled"] is True
    assert by_id["shai"]["always_enabled"] is True

    # Toggle a non-shai provider on and confirm it round-trips.
    put_provider = client.put(
        "/api/admin/ai-providers",
        json={"providers": [{"provider": "kiro", "enabled": True}]},
        headers=admin_headers,
    )
    assert put_provider.status_code == status.HTTP_200_OK
    kiro_after = {p["provider"]: p for p in put_provider.json()["providers"]}["kiro"]
    assert kiro_after["enabled"] is True

    # The forum flag is untouched by the AI provider write.
    assert client.get("/api/forum/config").json() == {"view_button_enabled": False}

    # Forum ON -> public read reports True again (button restored).
    client.put(
        "/api/admin/forum-config",
        json={"view_button_enabled": True},
        headers=admin_headers,
    )
    assert client.get("/api/forum/config").json() == {"view_button_enabled": True}

    # AI provider state is still what we set, independent of the forum toggle.
    providers_final = client.get("/api/admin/ai-providers", headers=admin_headers)
    kiro_final = {p["provider"]: p for p in providers_final.json()["providers"]}["kiro"]
    assert kiro_final["enabled"] is True


# ---------------------------------------------------------------------------
# /publichtml endpoint unchanged
# ---------------------------------------------------------------------------


def test_publichtml_serves_topic_unchanged(client, db_session, admin_headers):
    """The public HTML topic page still serves and is not gated by the flag.

    Confirms GET /api/forum/topics/{id}/publichtml returns 200 with an HTML
    content type for a real topic, and that disabling the forum "View" button
    setting does not affect this endpoint.

    Validates Requirement 3.5
    """
    # Create an author and a topic (the publichtml handler needs a Topic row;
    # posts are optional - it falls back to a default description with none).
    author = User(
        email="topic_author@test.com",
        password_hash="hashed_password",
        first_name="Topic",
        last_name="Author",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(author)
    db_session.commit()
    db_session.refresh(author)

    topic = Topic(
        title="Public HTML Topic",
        author_id=author.id,
        is_pinned=False,
        is_locked=False,
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)

    # Endpoint serves the HTML page.
    response = client.get(f"/api/forum/topics/{topic.id}/publichtml")
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("text/html")
    assert "Public HTML Topic" in response.text

    # Disabling the forum "View" button flag must not affect this endpoint.
    client.put(
        "/api/admin/forum-config",
        json={"view_button_enabled": False},
        headers=admin_headers,
    )
    response_after = client.get(f"/api/forum/topics/{topic.id}/publichtml")
    assert response_after.status_code == status.HTTP_200_OK
    assert response_after.headers["content-type"].startswith("text/html")
    assert "Public HTML Topic" in response_after.text

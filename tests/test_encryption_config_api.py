"""Integration tests for the admin encryption-config API (Task 5).

Exercises GET/PUT /api/admin/encryption-config through the FastAPI TestClient
(in-memory SQLite from tests/conftest.py). Follows the admin-fixture pattern
from tests/test_forum_config_integration.py.

Validates:
- GET defaults to {enabled: false, key_is_set: false}.
- PUT sets the key (key_is_set true) and writes an audit log entry.
- A later PUT with a mismatching key is rejected (400).
- Non-admin / unauthenticated access is forbidden (403).
- Responses never leak the password key, verification hash, or salt.
"""
import pytest
from fastapi import status

from app.models import User, UserRole, AuditLog
from app.auth.token import create_access_token
from app.security.key_provider import key_provider
from app.security import config_service


@pytest.fixture(autouse=True)
def _clear_key_provider():
    key_provider.clear()
    config_service._invalidate_cache()
    yield
    key_provider.clear()
    config_service._invalidate_cache()


@pytest.fixture
def administrator(db_session):
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
    token = create_access_token({"sub": str(administrator.id)})
    return {"Authorization": f"Bearer {token}"}


def test_get_defaults_off(client, admin_headers):
    response = client.get("/api/admin/encryption-config", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"enabled": False, "key_is_set": False}


def test_get_requires_authentication(client):
    assert client.get("/api/admin/encryption-config").status_code == status.HTTP_403_FORBIDDEN


def test_get_forbidden_for_member(client, auth_headers):
    response = client.get("/api/admin/encryption-config", headers=auth_headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_put_forbidden_for_member(client, auth_headers):
    response = client.put(
        "/api/admin/encryption-config",
        json={"password_key": "supersecret", "enabled": True},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_put_sets_key_and_audits(client, admin_headers, db_session):
    response = client.put(
        "/api/admin/encryption-config",
        json={"password_key": "supersecret", "enabled": True},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["key_is_set"] is True
    # enabled flag is NOT flipped by the API (migration script does that).
    assert body["enabled"] is False
    # Response never leaks secrets.
    assert set(body.keys()) == {"enabled", "key_is_set"}

    # The in-memory key provider is now active for the process.
    assert key_provider.is_active() is True

    # An audit entry was written and does not contain the key.
    entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "update_encryption_config")
        .first()
    )
    assert entry is not None
    assert "supersecret" not in str(entry.details)


def test_put_rejects_mismatched_key(client, admin_headers):
    # First set the key.
    client.put(
        "/api/admin/encryption-config",
        json={"password_key": "supersecret", "enabled": True},
        headers=admin_headers,
    )
    # A second PUT with a different key is rejected.
    response = client.put(
        "/api/admin/encryption-config",
        json={"password_key": "different-key", "enabled": True},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_put_accepts_matching_key_again(client, admin_headers):
    client.put(
        "/api/admin/encryption-config",
        json={"password_key": "supersecret", "enabled": True},
        headers=admin_headers,
    )
    response = client.put(
        "/api/admin/encryption-config",
        json={"password_key": "supersecret", "enabled": True},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["key_is_set"] is True


def test_put_rejects_short_key(client, admin_headers):
    # The project's validation exception handler normalises pydantic 422s to a
    # 400 Bad Request with a structured error body.
    response = client.put(
        "/api/admin/encryption-config",
        json={"password_key": "short", "enabled": True},
        headers=admin_headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

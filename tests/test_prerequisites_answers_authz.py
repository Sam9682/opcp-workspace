"""Example/edge-case unit tests for Q&A answer authorization and auth failures.

Spec: .kiro/specs/per-user-prerequisites-persistence (task 3.5)
Migrated by: .kiro/specs/vcf-prerequisites-update (task 6.1)
Updated by: .kiro/specs/opcp-installations-response-fields-editable (task 3.3)

These example tests pin the authorization boundary and auth-failure behavior of
the installation-scoped Q&A answer endpoints:

- Any authenticated user (administrators included) may PUT a Q&A answer: the PUT
  returns HTTP 200 and persists the row per installation (shared,
  last-write-wins). The previous admin-only block (HTTP 403
  ``ANSWER_NOT_ALLOWED_FOR_ADMIN``) has been removed.
- A missing or invalid Bearer token on the answer GET and PUT is rejected before
  any user identity is resolved: the read/write is never scoped to an
  unauthenticated caller.

Validates: Requirements 2.1, 2.3, 3.1
"""
import pytest
from fastapi import status

from app.models import User, UserRole
from app.auth.token import create_access_token


# Q&A slugs, kept in sync with app/prerequisites/router.py QA_SLUGS.
QA_SLUGS = ("network-checklist", "core-control-plane", "cloudstore", "vcf")


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/test_prerequisites_unit.py conventions)
# ---------------------------------------------------------------------------
@pytest.fixture
def admin_user(db_session):
    """Create an administrator user (now allowed to submit Q&A answers)."""
    user = User(
        email="admin@prereq.authz.test",
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
def member_user(db_session):
    """Create a member user (allowed to read and to PUT answers)."""
    user = User(
        email="member@prereq.authz.test",
        password_hash="hashed_password",
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _headers(user):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _error_code(body: dict) -> str | None:
    """Extract the structured error code from a router error body.

    The app installs an exception handler that unwraps ``ErrorResponse.create``
    to a top-level ``{"error": {"code": ...}}`` body. Fall back to the raw
    ``{"detail": {"error": {...}}}`` shape if the handler is not applied.
    """
    if isinstance(body.get("error"), dict):
        return body["error"].get("code")
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("error", {}).get("code")
    return None


# ===========================================================================
# Requirements 2.1, 2.3, 3.1: An authenticated administrator PUT to a Q&A slug
# now succeeds (HTTP 200) and persists the row per installation.
# ===========================================================================
class TestAdminAnswerAllowed:
    @pytest.mark.parametrize("slug", QA_SLUGS)
    def test_admin_put_answer_succeeds_for_each_qa_slug(
        self, client, admin_user, installation_id, slug
    ):
        """An admin PUT to any Q&A slug -> 200 success (admin block removed)."""
        resp = client.put(
            f"/api/prerequisites/installations/{installation_id}/{slug}/answers/row-1",
            json={"answer": "value"},
            headers=_headers(admin_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["success"] is True
        assert body["slug"] == slug

    def test_admin_put_answer_persists(
        self, client, admin_user, member_user, installation_id
    ):
        """An accepted admin PUT persists the row per installation (shared).

        A member GET for the same installation + slug reflects the admin-written
        value, confirming answers are shared per installation (no user scope).
        """
        put_resp = client.put(
            f"/api/prerequisites/installations/{installation_id}/cloudstore/answers/cs-1",
            json={"answer": "admin-written"},
            headers=_headers(admin_user),
        )
        assert put_resp.status_code == status.HTTP_200_OK
        get_resp = client.get(
            f"/api/prerequisites/installations/{installation_id}/cloudstore/answers",
            headers=_headers(member_user),
        )
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["answers"] == {"cs-1": "admin-written"}


# ===========================================================================
# Requirement 5.3: Missing/invalid Bearer token on GET and PUT answers -> 401
# ===========================================================================
class TestAnswersUnauthenticated:
    """Auth is enforced BEFORE any installation lookup, so these use a valid
    installation path shape; the caller is rejected on the missing/invalid
    token regardless of whether the installation exists."""

    def test_get_answers_missing_token_rejected(self, client, installation_id):
        """No Authorization header on GET answers -> not authorized (401/403)."""
        resp = client.get(
            f"/api/prerequisites/installations/{installation_id}/cloudstore/answers"
        )
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_get_answers_invalid_token_401(self, client, installation_id):
        """An invalid Bearer token on GET answers -> 401."""
        resp = client.get(
            f"/api/prerequisites/installations/{installation_id}/cloudstore/answers",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_put_answer_missing_token_rejected(self, client, installation_id):
        """No Authorization header on PUT answer -> not authorized (401/403)."""
        resp = client.put(
            f"/api/prerequisites/installations/{installation_id}/cloudstore/answers/cs-1",
            json={"answer": "value"},
        )
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_put_answer_invalid_token_401(self, client, installation_id):
        """An invalid Bearer token on PUT answer -> 401."""
        resp = client.put(
            f"/api/prerequisites/installations/{installation_id}/cloudstore/answers/cs-1",
            json={"answer": "value"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token_get_answers_does_not_leak_answers(
        self, client, installation_id
    ):
        """An unauthenticated GET never returns an answer map."""
        resp = client.get(
            f"/api/prerequisites/installations/{installation_id}/cloudstore/answers",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "answers" not in resp.json()

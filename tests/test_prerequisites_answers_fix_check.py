"""Bug-condition exploration / fix-checking tests for admin answer saves.

Bugfix spec: .kiro/specs/opcp-installations-response-fields-editable (task 1)

Property 1: Bug Condition — Editable and Persistable "Réponse client" for Any
Authenticated User.

These assertions encode the EXPECTED (post-fix) behavior: an authenticated
administrator may PUT a "Réponse client" value to any QA slug, the request
returns HTTP 200, and the value is persisted per installation (upserted with
``updated_by`` set). On the UNFIXED code they MUST FAIL, because
``get_answering_member`` in ``app/prerequisites/router.py`` rejects
administrators with HTTP 403 ``ANSWER_NOT_ALLOWED_FOR_ADMIN``.

Scoped-PBT: the bug condition is deterministic — an authenticated administrator
saving on a QA slug. We scope to the concrete failing cases: an authenticated
administrator across the four QA slugs.

Validates: Requirements 2.1, 2.3, 2.6, 3.1
"""
import pytest
from fastapi import status

from app.models import User, UserRole
from app.models.prerequisite import PrerequisiteAnswer
from app.auth.token import create_access_token


# QA slugs, kept in sync with app/prerequisites/router.py QA_SLUGS.
QA_SLUGS = ("network-checklist", "core-control-plane", "cloudstore", "vcf")


@pytest.fixture
def admin_user(db_session):
    """Create an administrator user (the intended editor after the fix)."""
    user = User(
        email="admin@prereq.fixcheck.test",
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


def _headers(user):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _answer_path(installation_id, slug, row_id):
    return (
        f"/api/prerequisites/installations/{installation_id}"
        f"/{slug}/answers/{row_id}"
    )


def _answers_path(installation_id, slug):
    return f"/api/prerequisites/installations/{installation_id}/{slug}/answers"


class TestAdminAnswerPersistsAfterFix:
    """Property 1: an authenticated admin PUT to a QA slug succeeds and persists."""

    @pytest.mark.parametrize("slug", QA_SLUGS)
    def test_admin_put_answer_returns_200_for_each_qa_slug(
        self, client, admin_user, installation_id, slug
    ):
        """Admin PUT to any QA slug -> 200 (fails on unfixed code with 403)."""
        resp = client.put(
            _answer_path(installation_id, slug, "row-1"),
            json={"answer": "admin-value"},
            headers=_headers(admin_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["success"] is True
        assert body["slug"] == slug

    @pytest.mark.parametrize("slug", QA_SLUGS)
    def test_admin_answer_persists_and_records_updated_by(
        self, client, db_session, admin_user, installation_id, slug
    ):
        """A successful admin PUT upserts the row with updated_by == admin id."""
        client.put(
            _answer_path(installation_id, slug, "row-persist"),
            json={"answer": "persisted-by-admin"},
            headers=_headers(admin_user),
        )

        # The value is visible on GET (persisted per installation).
        get_resp = client.get(
            _answers_path(installation_id, slug), headers=_headers(admin_user)
        )
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["answers"] == {"row-persist": "persisted-by-admin"}

        # And the last-editor is recorded on the row.
        row = (
            db_session.query(PrerequisiteAnswer)
            .filter(
                PrerequisiteAnswer.slug == slug,
                PrerequisiteAnswer.row_id == "row-persist",
            )
            .first()
        )
        assert row is not None
        assert row.answer == "persisted-by-admin"
        assert row.updated_by == admin_user.id

"""Unit tests for the prerequisites route family (models, endpoints, slug
validation, and authorization), migrated to the installation-scoped contract.

Bugfix spec: .kiro/specs/basics-prerequisites-404-fix (task 3.6)
Migrated by: .kiro/specs/vcf-prerequisites-update (task 6.1)

The parent spec ``multi-instance-opcp-prerequisites`` re-scoped the prerequisites
family under an installation. These tests now exercise:

- Model behavior: defaults, ``updated_at`` default/onupdate, and the
  ``(installation_id, slug, row_id)`` unique constraint on ``PrerequisiteAnswer``
  (answers are shared per installation; there is no ``user_id`` scope). Content
  is keyed by ``(installation_id, slug)``.
- Router per-endpoint: correct status/body for each installation-scoped endpoint
  for known slugs.
- Slug validation: unknown slug under a valid installation -> resource-specific
  404 carrying ``PREREQUISITE_SLUG_NOT_FOUND``; unknown installation ->
  ``INSTALLATION_NOT_FOUND``; empty-content default for a never-saved known
  static slug.
- Authorization: admin-only static PUT (403 for member), answer PUT allowed for
  any authenticated user (administrators included, HTTP 200), 401 for
  unauthenticated / invalid-token reads.

Updated by: .kiro/specs/opcp-installations-response-fields-editable (task 3.3)

Validates: Requirements 9.3, 7.7 (and, unchanged in intent, 2.1-2.6, 7.1-7.5)
"""
import time

import pytest
from fastapi import status
from sqlalchemy.exc import IntegrityError

from app.models import User, UserRole
from app.models.prerequisite import PrerequisiteContent, PrerequisiteAnswer
from app.auth.token import create_access_token

from tests.conftest import create_installation


# --- Known slug sets (kept in sync with app/prerequisites/router.py) ---
STATIC_SLUGS = ("basics", "network-flux")
QA_SLUGS = ("network-checklist", "core-control-plane", "cloudstore", "vcf")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def admin_user(db_session):
    """Create an administrator user (allowed to PUT static content)."""
    user = User(
        email="admin@prereq.test",
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
        email="member@prereq.test",
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


def _content_path(installation_id, slug):
    return f"/api/prerequisites/installations/{installation_id}/{slug}/content"


def _answers_path(installation_id, slug):
    return f"/api/prerequisites/installations/{installation_id}/{slug}/answers"


def _answer_path(installation_id, slug, row_id):
    return (
        f"/api/prerequisites/installations/{installation_id}"
        f"/{slug}/answers/{row_id}"
    )


def _error_code(body: dict) -> str | None:
    """Extract the structured error code from a router error body."""
    if isinstance(body.get("error"), dict):
        return body["error"].get("code")
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("error", {}).get("code")
    return None


# ===========================================================================
# Model behavior
# ===========================================================================
class TestPrerequisiteContentModel:
    def test_content_defaults_to_empty_string(self, db_session):
        """content defaults to "" when not provided."""
        inst = create_installation(db_session)
        row = PrerequisiteContent(installation_id=inst.id, slug="basics")
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        assert row.content == ""

    def test_updated_at_set_on_insert(self, db_session):
        """updated_at is populated on insert."""
        inst = create_installation(db_session)
        row = PrerequisiteContent(
            installation_id=inst.id, slug="basics", content="hello"
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        assert row.updated_at is not None

    def test_updated_at_changes_on_update(self, db_session):
        """updated_at advances on update (onupdate)."""
        inst = create_installation(db_session)
        row = PrerequisiteContent(
            installation_id=inst.id, slug="basics", content="v1"
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        first = row.updated_at

        time.sleep(0.01)
        row.content = "v2"
        db_session.commit()
        db_session.refresh(row)

        assert row.updated_at >= first
        assert row.updated_at != first

    def test_installation_slug_unique_constraint(self, db_session):
        """A second content row for the same (installation_id, slug) is rejected."""
        inst = create_installation(db_session)
        db_session.add(
            PrerequisiteContent(installation_id=inst.id, slug="basics", content="a")
        )
        db_session.commit()

        db_session.add(
            PrerequisiteContent(installation_id=inst.id, slug="basics", content="b")
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_same_slug_different_installation_allowed(self, db_session):
        """Two installations may each hold their own content for the same slug."""
        inst_a = create_installation(db_session, "A")
        inst_b = create_installation(db_session, "B")
        db_session.add(
            PrerequisiteContent(installation_id=inst_a.id, slug="basics", content="a")
        )
        db_session.add(
            PrerequisiteContent(installation_id=inst_b.id, slug="basics", content="b")
        )
        db_session.commit()  # must not raise
        rows = db_session.query(PrerequisiteContent).filter(
            PrerequisiteContent.slug == "basics"
        ).all()
        assert len(rows) == 2


class TestPrerequisiteAnswerModel:
    """Model behavior for the installation-scoped answer schema.

    Per the multi-instance re-scope, ``PrerequisiteAnswer`` carries a non-null
    ``installation_id`` FK and its uniqueness key is
    ``(installation_id, slug, row_id)`` (answers are shared per installation,
    last-write-wins; there is no ``user_id`` scope). Each test seeds a real
    owning Installation so the non-null FK is satisfied.
    """

    def test_answer_defaults_to_empty_string(self, db_session):
        """answer defaults to "" when not provided."""
        inst = create_installation(db_session)
        row = PrerequisiteAnswer(
            installation_id=inst.id, slug="cloudstore", row_id="cs-subnet-cidr"
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        assert row.answer == ""

    def test_updated_at_set_on_insert(self, db_session):
        inst = create_installation(db_session)
        row = PrerequisiteAnswer(
            installation_id=inst.id, slug="cloudstore", row_id="cs-1", answer="a"
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        assert row.updated_at is not None

    def test_updated_at_changes_on_update(self, db_session):
        inst = create_installation(db_session)
        row = PrerequisiteAnswer(
            installation_id=inst.id, slug="cloudstore", row_id="cs-1", answer="a"
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        first = row.updated_at

        time.sleep(0.01)
        row.answer = "b"
        db_session.commit()
        db_session.refresh(row)

        assert row.updated_at >= first
        assert row.updated_at != first

    def test_installation_slug_row_id_unique_constraint(self, db_session):
        """A second insert with the same (installation_id, slug, row_id) raises.

        Uniqueness is keyed per installation, so a duplicate for the SAME
        installation is rejected.
        """
        inst = create_installation(db_session)
        db_session.add(
            PrerequisiteAnswer(
                installation_id=inst.id, slug="cloudstore", row_id="cs-1", answer="a"
            )
        )
        db_session.commit()

        db_session.add(
            PrerequisiteAnswer(
                installation_id=inst.id, slug="cloudstore", row_id="cs-1", answer="b"
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_same_slug_row_id_different_installation_allowed(self, db_session):
        """Two installations may each hold their own answer for the same (slug, row_id).

        The uniqueness key includes ``installation_id``, so per-installation rows
        for an identical (slug, row_id) coexist.
        """
        inst_a = create_installation(db_session, "A")
        inst_b = create_installation(db_session, "B")
        db_session.add(
            PrerequisiteAnswer(
                installation_id=inst_a.id, slug="cloudstore", row_id="shared", answer="a"
            )
        )
        db_session.add(
            PrerequisiteAnswer(
                installation_id=inst_b.id, slug="cloudstore", row_id="shared", answer="b"
            )
        )
        db_session.commit()  # must not raise
        rows = db_session.query(PrerequisiteAnswer).filter(
            PrerequisiteAnswer.slug == "cloudstore",
            PrerequisiteAnswer.row_id == "shared",
        ).all()
        assert len(rows) == 2

    def test_same_row_id_different_slug_allowed(self, db_session):
        """The unique constraint is on the tuple, not row_id alone."""
        inst = create_installation(db_session)
        db_session.add(
            PrerequisiteAnswer(
                installation_id=inst.id, slug="cloudstore", row_id="shared", answer="a"
            )
        )
        db_session.add(
            PrerequisiteAnswer(
                installation_id=inst.id, slug="vcf", row_id="shared", answer="b"
            )
        )
        db_session.commit()  # must not raise
        rows = db_session.query(PrerequisiteAnswer).filter(
            PrerequisiteAnswer.row_id == "shared"
        ).all()
        assert len(rows) == 2


# ===========================================================================
# Router: per-endpoint happy paths for known slugs
# ===========================================================================
class TestEndpointsKnownSlugs:
    def test_get_content_returns_shape(self, client, member_user, installation_id):
        """GET content -> 200 with {slug, content, updated_at}."""
        resp = client.get(
            _content_path(installation_id, "basics"), headers=_headers(member_user)
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["slug"] == "basics"
        assert "content" in body
        assert "updated_at" in body

    def test_get_answers_returns_shape(self, client, member_user, installation_id):
        """GET answers -> 200 with {slug, answers} (empty map when none)."""
        resp = client.get(
            _answers_path(installation_id, "network-checklist"),
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["slug"] == "network-checklist"
        assert body["answers"] == {}

    def test_put_content_success_by_admin(
        self, client, admin_user, member_user, installation_id
    ):
        """PUT content by admin -> 200 success; GET reflects the saved value."""
        resp = client.put(
            _content_path(installation_id, "basics"),
            json={"content": "<p>saved</p>"},
            headers=_headers(admin_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["success"] is True
        assert body["slug"] == "basics"

        get_resp = client.get(
            _content_path(installation_id, "basics"), headers=_headers(member_user)
        )
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["content"] == "<p>saved</p>"

    def test_put_answer_success_by_member(self, client, member_user, installation_id):
        """PUT answer by member -> 200 success; GET reflects the saved map."""
        resp = client.put(
            _answer_path(installation_id, "cloudstore", "cs-subnet-cidr"),
            json={"answer": "10.0.0.0/24"},
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["success"] is True
        assert body["slug"] == "cloudstore"

        get_resp = client.get(
            _answers_path(installation_id, "cloudstore"),
            headers=_headers(member_user),
        )
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["answers"] == {"cs-subnet-cidr": "10.0.0.0/24"}

    def test_put_answer_upsert_updates_in_place(
        self, client, member_user, installation_id
    ):
        """A second PUT for the same (installation, slug, row_id) updates in place."""
        base = _answer_path(installation_id, "cloudstore", "cs-1")
        client.put(base, json={"answer": "first"}, headers=_headers(member_user))
        resp = client.put(
            base, json={"answer": "second"}, headers=_headers(member_user)
        )
        assert resp.status_code == status.HTTP_200_OK

        get_resp = client.get(
            _answers_path(installation_id, "cloudstore"),
            headers=_headers(member_user),
        )
        assert get_resp.json()["answers"] == {"cs-1": "second"}


# ===========================================================================
# Slug validation (and installation validation)
# ===========================================================================
class TestSlugValidation:
    def test_unknown_static_slug_get_content_resource_specific_404(
        self, client, member_user, installation_id
    ):
        """Unknown slug -> resource-specific 404 with PREREQUISITE_SLUG_NOT_FOUND."""
        resp = client.get(
            _content_path(installation_id, "does-not-exist"),
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        body = resp.json()
        assert body != {"detail": "Not Found"}
        assert _error_code(body) == "PREREQUISITE_SLUG_NOT_FOUND"

    def test_unknown_qa_slug_get_answers_resource_specific_404(
        self, client, member_user, installation_id
    ):
        resp = client.get(
            _answers_path(installation_id, "nope"), headers=_headers(member_user)
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        body = resp.json()
        assert body != {"detail": "Not Found"}
        assert _error_code(body) == "PREREQUISITE_SLUG_NOT_FOUND"

    def test_qa_slug_rejected_on_content_endpoint(
        self, client, member_user, installation_id
    ):
        """A qa slug is not a valid static-content slug -> 404."""
        resp = client.get(
            _content_path(installation_id, "cloudstore"),
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert _error_code(resp.json()) == "PREREQUISITE_SLUG_NOT_FOUND"

    def test_unknown_slug_put_content_resource_specific_404(
        self, client, admin_user, installation_id
    ):
        resp = client.put(
            _content_path(installation_id, "does-not-exist"),
            json={"content": "x"},
            headers=_headers(admin_user),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert _error_code(resp.json()) == "PREREQUISITE_SLUG_NOT_FOUND"

    def test_never_saved_known_static_slug_returns_empty_content(
        self, client, member_user, installation_id
    ):
        """Known static slug never saved -> 200 with content:"" default."""
        resp = client.get(
            _content_path(installation_id, "network-flux"),
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["slug"] == "network-flux"
        assert body["content"] == ""
        assert body["updated_at"] is None

    def test_unknown_installation_get_content_is_installation_not_found(
        self, client, member_user, unknown_installation_id
    ):
        """Unknown installation id on content GET -> INSTALLATION_NOT_FOUND (Req 7.6)."""
        resp = client.get(
            _content_path(unknown_installation_id, "basics"),
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert _error_code(resp.json()) == "INSTALLATION_NOT_FOUND"

    def test_unknown_installation_get_answers_is_installation_not_found(
        self, client, member_user, unknown_installation_id
    ):
        """Unknown installation id on answers GET -> INSTALLATION_NOT_FOUND (Req 7.6)."""
        resp = client.get(
            _answers_path(unknown_installation_id, "cloudstore"),
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert _error_code(resp.json()) == "INSTALLATION_NOT_FOUND"


# ===========================================================================
# Authorization
# ===========================================================================
class TestAuthorization:
    def test_put_content_forbidden_for_member(
        self, client, member_user, installation_id
    ):
        """Static PUT is admin-only -> 403 for a member."""
        resp = client.put(
            _content_path(installation_id, "basics"),
            json={"content": "x"},
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_put_answer_succeeds_for_admin(
        self, client, admin_user, installation_id
    ):
        """Answer PUT is allowed for any authenticated user -> 200 for an admin."""
        resp = client.put(
            _answer_path(installation_id, "cloudstore", "cs-1"),
            json={"answer": "x"},
            headers=_headers(admin_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["success"] is True
        assert body["slug"] == "cloudstore"

    def test_get_content_unauthenticated_401(self, client, installation_id):
        """No bearer token -> 401 on a read."""
        resp = client.get(_content_path(installation_id, "basics"))
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_get_answers_unauthenticated_401(self, client, installation_id):
        resp = client.get(_answers_path(installation_id, "network-checklist"))
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_get_content_invalid_token_401(self, client, installation_id):
        """Invalid bearer token -> 401 on a read."""
        resp = client.get(
            _content_path(installation_id, "basics"),
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# Installations CRUD (create/update/delete HTTP endpoints)
#
# Regression coverage for the "operation failed" create bug: the Installation
# model previously relied on a PostgreSQL ``server_default=func.now()`` for
# created_at/updated_at, but the multi-instance migration built those columns
# NOT NULL without any DB default, so every INSERT emitted NULL and hit a
# NotNullViolation. The model now sets them Python-side (like User/Topic/Post).
# These tests exercise the HTTP create path end-to-end.
# ===========================================================================
def _installations_path() -> str:
    return "/api/prerequisites/installations"


def _installation_path(installation_id) -> str:
    return f"/api/prerequisites/installations/{installation_id}"


class TestInstallationsCrud:
    def test_create_installation_by_admin_returns_201_with_timestamps(
        self, client, admin_user
    ):
        """POST /installations by admin -> 201 with a populated, valid body.

        Guards the create regression: created_at/updated_at must be populated
        without depending on a DB server default.
        """
        resp = client.post(
            _installations_path(),
            json={"project_name": "DEMO"},
            headers=_headers(admin_user),
        )
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["project_name"] == "DEMO"
        assert body["id"]
        # The two fields the NotNullViolation was raised on must be present.
        assert body["created_at"] is not None
        assert body["updated_at"] is not None

    def test_created_installation_appears_in_list(self, client, admin_user):
        """A freshly created installation is returned by the list endpoint."""
        create = client.post(
            _installations_path(),
            json={"project_name": "DEMO"},
            headers=_headers(admin_user),
        )
        assert create.status_code == status.HTTP_201_CREATED
        new_id = create.json()["id"]

        listing = client.get(_installations_path(), headers=_headers(admin_user))
        assert listing.status_code == status.HTTP_200_OK
        ids = [row["id"] for row in listing.json()["installations"]]
        assert new_id in ids

    def test_create_installation_forbidden_for_member(self, client, member_user):
        """POST /installations is admin-only -> 403 for a member."""
        resp = client.post(
            _installations_path(),
            json={"project_name": "DEMO"},
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_installation_blank_name_rejected(self, client, admin_user):
        """A blank/whitespace-only project_name is rejected as a validation error.

        The app registers a custom request-validation handler that returns 400
        (rather than FastAPI's default 422), so accept either.
        """
        resp = client.post(
            _installations_path(),
            json={"project_name": "   "},
            headers=_headers(admin_user),
        )
        assert resp.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    def test_update_installation_changes_project_name(self, client, admin_user):
        """PUT /installations/{id} by admin -> 200 with the renamed project."""
        create = client.post(
            _installations_path(),
            json={"project_name": "DEMO"},
            headers=_headers(admin_user),
        )
        new_id = create.json()["id"]

        resp = client.put(
            _installation_path(new_id),
            json={"project_name": "RENAMED"},
            headers=_headers(admin_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["project_name"] == "RENAMED"

    def test_delete_installation_removes_it(self, client, admin_user):
        """DELETE /installations/{id} by admin -> 204 and it leaves the list."""
        create = client.post(
            _installations_path(),
            json={"project_name": "DEMO"},
            headers=_headers(admin_user),
        )
        new_id = create.json()["id"]

        resp = client.delete(
            _installation_path(new_id), headers=_headers(admin_user)
        )
        assert resp.status_code == status.HTTP_204_NO_CONTENT

        listing = client.get(_installations_path(), headers=_headers(admin_user))
        ids = [row["id"] for row in listing.json()["installations"]]
        assert new_id not in ids

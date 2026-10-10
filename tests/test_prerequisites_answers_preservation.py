"""Preservation property tests for the admin-editable answers bugfix.

Bugfix spec: .kiro/specs/opcp-installations-response-fields-editable (task 2)

Property 2 (Preservation): every NON-bug-condition input must behave EXACTLY as
it does today after the fix relaxes ``get_answering_member`` to authorize any
authenticated user (removing the admin-only 403). The bug condition is an
authenticated ADMINISTRATOR saving on a QA slug; the complement covered here is:

  (a) an authenticated non-admin MEMBER PUT to a QA answers route -> 200, upserts
      the row (shared per installation, last-write-wins, ``updated_by`` recorded);
  (b) a missing / invalid Bearer token on GET and PUT answers -> 401 (rejected
      before any user identity is resolved);
  (c) an unknown installation id / unknown slug -> structured 404
      (``INSTALLATION_NOT_FOUND`` / ``PREREQUISITE_SLUG_NOT_FOUND``) on BOTH the
      load (GET) and save (PUT) paths;
  (d) admin-only static-content PUT and installation CRUD stay admin-only
      (403 for a member).

Methodology (observation-first): the assertions below encode behavior OBSERVED
on the CURRENT (unfixed) app through the conftest ``client`` fixture. They are
EXPECTED TO PASS now (capturing the baseline) and must CONTINUE to pass after the
fix (proving no regression for non-bug inputs). No application code is modified
by this task.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
"""
import pytest
from fastapi import status

from app.models import User, UserRole
from app.models.prerequisite import PrerequisiteAnswer
from app.auth.token import create_access_token

try:
    from hypothesis import given, settings, HealthCheck, strategies as st
    HAS_HYPOTHESIS = True
except Exception:  # pragma: no cover - hypothesis is expected to be installed
    HAS_HYPOTHESIS = False


# QA / static slugs, kept in sync with app/prerequisites/router.py.
QA_SLUGS = ("network-checklist", "core-control-plane", "cloudstore", "vcf")
STATIC_SLUGS = ("basics", "network-flux")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def member_user(db_session):
    """An authenticated non-admin member (the always-allowed editor)."""
    user = User(
        email="member@prereq.preservation.test",
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


@pytest.fixture
def other_member_user(db_session):
    """A second member, used to prove shared (not user-scoped) last-write-wins."""
    user = User(
        email="member2@prereq.preservation.test",
        password_hash="hashed_password",
        first_name="Member2",
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


def _answer_path(installation_id, slug, row_id):
    return (
        f"/api/prerequisites/installations/{installation_id}"
        f"/{slug}/answers/{row_id}"
    )


def _answers_path(installation_id, slug):
    return f"/api/prerequisites/installations/{installation_id}/{slug}/answers"


def _content_path(installation_id, slug):
    return f"/api/prerequisites/installations/{installation_id}/{slug}/content"


def _error_code(body: dict) -> str | None:
    """Extract the structured error code from a router error body."""
    if isinstance(body.get("error"), dict):
        return body["error"].get("code")
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("error", {}).get("code")
    return None


# ===========================================================================
# (a) Member answer PUT: succeeds, upserts, shared per installation,
#     last-write-wins, records updated_by. (Req 3.1, 3.2)
# ===========================================================================
class TestMemberSavePreserved:
    @pytest.mark.parametrize("slug", QA_SLUGS)
    def test_member_put_answer_returns_200_and_persists_with_updated_by(
        self, client, db_session, member_user, installation_id, slug
    ):
        """A member PUT to any QA slug -> 200; the row is upserted with updated_by."""
        resp = client.put(
            _answer_path(installation_id, slug, "row-a"),
            json={"answer": "member-value"},
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["success"] is True
        assert body["slug"] == slug

        get_resp = client.get(
            _answers_path(installation_id, slug), headers=_headers(member_user)
        )
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["answers"] == {"row-a": "member-value"}

        row = (
            db_session.query(PrerequisiteAnswer)
            .filter(
                PrerequisiteAnswer.slug == slug,
                PrerequisiteAnswer.row_id == "row-a",
            )
            .first()
        )
        assert row is not None
        assert row.answer == "member-value"
        assert row.updated_by == member_user.id

    def test_member_answer_is_shared_last_write_wins(
        self, client, db_session, member_user, other_member_user, installation_id
    ):
        """Two members writing the same (installation, slug, row) -> shared, last wins.

        The answer is NOT user-scoped: the second write overwrites the first in
        place, and updated_by records the last editor.
        """
        path = _answer_path(installation_id, "cloudstore", "shared-row")
        client.put(path, json={"answer": "first"}, headers=_headers(member_user))
        client.put(
            path, json={"answer": "second"}, headers=_headers(other_member_user)
        )

        get_resp = client.get(
            _answers_path(installation_id, "cloudstore"),
            headers=_headers(member_user),
        )
        assert get_resp.json()["answers"] == {"shared-row": "second"}

        rows = (
            db_session.query(PrerequisiteAnswer)
            .filter(
                PrerequisiteAnswer.slug == "cloudstore",
                PrerequisiteAnswer.row_id == "shared-row",
            )
            .all()
        )
        # Exactly one shared row (no per-user duplication), last editor recorded.
        assert len(rows) == 1
        assert rows[0].answer == "second"
        assert rows[0].updated_by == other_member_user.id


# ===========================================================================
# (b) Missing / invalid Bearer token -> 401 on GET and PUT answers. (Req 3.6 auth)
# ===========================================================================
class TestUnauthenticatedRejectedPreserved:
    def test_get_answers_missing_token_rejected(self, client, installation_id):
        resp = client.get(_answers_path(installation_id, "cloudstore"))
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_get_answers_invalid_token_401(self, client, installation_id):
        resp = client.get(
            _answers_path(installation_id, "cloudstore"),
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_put_answer_missing_token_rejected(self, client, installation_id):
        resp = client.put(
            _answer_path(installation_id, "cloudstore", "cs-1"),
            json={"answer": "value"},
        )
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_put_answer_invalid_token_401(self, client, installation_id):
        resp = client.put(
            _answer_path(installation_id, "cloudstore", "cs-1"),
            json={"answer": "value"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token_put_answer_does_not_persist(
        self, client, db_session, installation_id
    ):
        """A rejected (invalid-token) PUT must not create any row."""
        client.put(
            _answer_path(installation_id, "cloudstore", "leak-row"),
            json={"answer": "should-not-write"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        row = (
            db_session.query(PrerequisiteAnswer)
            .filter(PrerequisiteAnswer.row_id == "leak-row")
            .first()
        )
        assert row is None


# ===========================================================================
# (c) Structured 404 on load AND save for unknown installation / unknown slug.
#     (Req 3.6)
# ===========================================================================
class TestStructured404Preserved:
    def test_unknown_installation_get_answers_404(
        self, client, member_user, unknown_installation_id
    ):
        resp = client.get(
            _answers_path(unknown_installation_id, "cloudstore"),
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert _error_code(resp.json()) == "INSTALLATION_NOT_FOUND"

    def test_unknown_installation_put_answer_404(
        self, client, member_user, unknown_installation_id
    ):
        """Save-side unknown installation -> INSTALLATION_NOT_FOUND (member auth passes)."""
        resp = client.put(
            _answer_path(unknown_installation_id, "cloudstore", "cs-1"),
            json={"answer": "value"},
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert _error_code(resp.json()) == "INSTALLATION_NOT_FOUND"

    def test_unknown_slug_get_answers_404(
        self, client, member_user, installation_id
    ):
        resp = client.get(
            _answers_path(installation_id, "not-a-real-slug"),
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert _error_code(resp.json()) == "PREREQUISITE_SLUG_NOT_FOUND"

    def test_unknown_slug_put_answer_404(
        self, client, member_user, installation_id
    ):
        """Save-side unknown slug -> PREREQUISITE_SLUG_NOT_FOUND (member auth passes)."""
        resp = client.put(
            _answer_path(installation_id, "not-a-real-slug", "row-1"),
            json={"answer": "value"},
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert _error_code(resp.json()) == "PREREQUISITE_SLUG_NOT_FOUND"


# ===========================================================================
# (d) Admin-only static content PUT and installation CRUD stay admin-only.
#     (Req 3.7)
# ===========================================================================
class TestAdminOnlyMutationsPreserved:
    @pytest.mark.parametrize("slug", STATIC_SLUGS)
    def test_static_content_put_forbidden_for_member(
        self, client, member_user, installation_id, slug
    ):
        """Static content PUT is admin-only -> 403 for a member (unchanged)."""
        resp = client.put(
            _content_path(installation_id, slug),
            json={"content": "<p>member should not write</p>"},
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_installation_forbidden_for_member(self, client, member_user):
        resp = client.post(
            "/api/prerequisites/installations",
            json={"project_name": "DEMO"},
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_update_installation_forbidden_for_member(
        self, client, member_user, installation_id
    ):
        resp = client.put(
            f"/api/prerequisites/installations/{installation_id}",
            json={"project_name": "RENAMED"},
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_installation_forbidden_for_member(
        self, client, member_user, installation_id
    ):
        resp = client.delete(
            f"/api/prerequisites/installations/{installation_id}",
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# Property-based preservation: for MANY generated (slug, row_id, value) tuples a
# member PUT round-trips to a GET unchanged (upsert + shared per-installation
# read contract), across the QA input domain. This is the general form of the
# member-save preservation the fix must not disturb.
# ===========================================================================
if HAS_HYPOTHESIS:

    _ROW_ID = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
        min_size=1,
        max_size=24,
    )
    # Answer values include empty strings and arbitrary unicode text; the answer
    # is stored verbatim (no coercion at the API layer).
    _ANSWER = st.text(max_size=64)

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(slug=st.sampled_from(QA_SLUGS), row_id=_ROW_ID, value=_ANSWER)
    def test_member_put_then_get_roundtrips(
        client, member_user, installation_id, slug, row_id, value
    ):
        """Property: a member PUT of (slug, row_id, value) is readable verbatim on GET.

        Preserves the shared per-installation upsert + ``{ row_id: answer }`` load
        contract for the whole QA input domain.

        Validates: Requirements 3.1, 3.2
        """
        put_resp = client.put(
            _answer_path(installation_id, slug, row_id),
            json={"answer": value},
            headers=_headers(member_user),
        )
        assert put_resp.status_code == status.HTTP_200_OK
        assert put_resp.json()["success"] is True

        get_resp = client.get(
            _answers_path(installation_id, slug), headers=_headers(member_user)
        )
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["answers"].get(row_id) == value

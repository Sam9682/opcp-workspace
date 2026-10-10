"""Integration tests for the prerequisites route family: full round-trip
through the FastAPI ``TestClient`` with real JWT auth.

Bugfix spec: .kiro/specs/basics-prerequisites-404-fix (task 5)
Migrated by: .kiro/specs/vcf-prerequisites-update (task 6.1)

These tests exercise end-to-end flows against the installation-scoped app
(router mounted, persistence models created via the ``Base.metadata.create_all``
fixture in ``tests/conftest.py``). They use real ``Authorization: Bearer <jwt>``
headers (no dependency overrides for auth) so the auth wiring is validated too.

Covered flows:
- Static flow: an admin saves ``basics`` content under an installation, a member
  loads it and receives the persisted value with a 200 (never a 404 or error
  that would trip the frontend load-error banner). The content round-trips
  exactly.
- Answer flow: a member writes several ``cloudstore`` answers under one
  installation, reloads them (answers are shared per installation), and answers
  are isolated ACROSS installations — content/answers written under one
  installation never appear in reads scoped to another (design Property 9).

Validates: Requirements 9.3, 7.7
"""
import pytest
from fastapi import status

from app.models import User, UserRole
from app.auth.token import create_access_token

from tests.conftest import create_installation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def admin_user(db_session):
    """Create an administrator user (allowed to PUT static content)."""
    user = User(
        email="admin@prereq.integration.test",
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
    """Create the first member user (writes answers, reads content)."""
    user = User(
        email="member-a@prereq.integration.test",
        password_hash="hashed_password",
        first_name="Member",
        last_name="Alpha",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def member_user_b(db_session):
    """Create a SECOND, distinct member user (distinct session / JWT).

    Used to confirm answers are SHARED per installation (both members see the
    same installation-scoped map), not per-user.
    """
    user = User(
        email="member-b@prereq.integration.test",
        password_hash="hashed_password",
        first_name="Member",
        last_name="Bravo",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def installation_b(db_session):
    """Create a SECOND, distinct installation for cross-installation isolation."""
    return create_installation(db_session, "Second Installation")


def _headers(user):
    """Build a real bearer-token header for the given user."""
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


# ===========================================================================
# Static flow: admin saves -> member loads persisted value (no load error)
# ===========================================================================
class TestStaticContentRoundTrip:
    def test_admin_save_then_member_load_round_trips_exactly(
        self, client, admin_user, member_user, installation_id
    ):
        """Admin PUTs basics content; a member GETs the exact persisted value.

        The GET returns 200 with the exact content (never a 404 / error that
        would trigger the frontend load-error banner).
        """
        content = "<h1>OPCP Basics</h1><p>Some rich <b>content</b> &amp; notes.</p>"

        put_resp = client.put(
            _content_path(installation_id, "basics"),
            json={"content": content},
            headers=_headers(admin_user),
        )
        assert put_resp.status_code == status.HTTP_200_OK
        assert put_resp.json()["success"] is True

        # A different session (a member) loads the content.
        get_resp = client.get(
            _content_path(installation_id, "basics"),
            headers=_headers(member_user),
        )

        # 200, not a 404 or error -> the load-error banner never triggers.
        assert get_resp.status_code == status.HTTP_200_OK
        body = get_resp.json()
        assert body["slug"] == "basics"
        # The persisted content round-trips exactly (byte-for-byte).
        assert body["content"] == content
        assert body["updated_at"] is not None

    def test_never_saved_slug_loads_empty_default_not_error(
        self, client, member_user, installation_id
    ):
        """A never-saved known static slug returns a 200 empty default.

        This is the key anti-banner behavior: a first-visit page renders
        cleanly (200, content:"") instead of surfacing an error.
        """
        resp = client.get(
            _content_path(installation_id, "network-flux"),
            headers=_headers(member_user),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["slug"] == "network-flux"
        assert body["content"] == ""
        assert body["updated_at"] is None

    def test_admin_overwrite_is_reflected_on_reload(
        self, client, admin_user, member_user, installation_id
    ):
        """A second admin save overwrites; the member reload shows the update."""
        first = "<p>version one</p>"
        second = "<p>version two - updated</p>"

        client.put(
            _content_path(installation_id, "basics"),
            json={"content": first},
            headers=_headers(admin_user),
        )
        client.put(
            _content_path(installation_id, "basics"),
            json={"content": second},
            headers=_headers(admin_user),
        )

        get_resp = client.get(
            _content_path(installation_id, "basics"),
            headers=_headers(member_user),
        )
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["content"] == second


# ===========================================================================
# Answer flow: shared per installation; isolated across installations
# ===========================================================================
class TestAnswerRoundTripAndSharing:
    def test_member_saves_several_answers_and_reload_returns_same_map(
        self, client, member_user, installation_id
    ):
        """Member PUTs several cloudstore answers; GET returns the same map."""
        answers = {
            "cs-subnet-cidr": "10.0.0.0/24",
            "cs-region": "eu-west-1",
            "cs-bucket-name": "opcp-artifacts",
        }
        for row_id, answer in answers.items():
            resp = client.put(
                _answer_path(installation_id, "cloudstore", row_id),
                json={"answer": answer},
                headers=_headers(member_user),
            )
            assert resp.status_code == status.HTTP_200_OK
            assert resp.json()["success"] is True

        get_resp = client.get(
            _answers_path(installation_id, "cloudstore"),
            headers=_headers(member_user),
        )
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["answers"] == answers

    def test_answers_are_shared_across_members_within_an_installation(
        self, client, member_user, member_user_b, installation_id
    ):
        """Answers are shared per installation: a second member sees member A's
        writes and a write by B is last-write-wins on the shared row.

        Under the multi-instance re-scope answers are keyed by
        (installation_id, slug, row_id) with no per-user scope, so both members
        observe one shared installation-scoped map.
        """
        assert member_user.id != member_user_b.id

        a_answers = {
            "cs-subnet-cidr": "172.16.0.0/16",
            "cs-region": "us-east-2",
        }
        for row_id, answer in a_answers.items():
            resp = client.put(
                _answer_path(installation_id, "cloudstore", row_id),
                json={"answer": answer},
                headers=_headers(member_user),
            )
            assert resp.status_code == status.HTTP_200_OK

        # Member B reads the SAME installation and sees member A's shared answers.
        b_get = client.get(
            _answers_path(installation_id, "cloudstore"),
            headers=_headers(member_user_b),
        )
        assert b_get.status_code == status.HTTP_200_OK
        assert b_get.json()["answers"] == a_answers

        # Member B writes the shared row -> last-write-wins on the shared value.
        b_put = client.put(
            _answer_path(installation_id, "cloudstore", "cs-region"),
            json={"answer": "b-shared-value"},
            headers=_headers(member_user_b),
        )
        assert b_put.status_code == status.HTTP_200_OK

        # Member A now observes member B's write on the shared row.
        a_get = client.get(
            _answers_path(installation_id, "cloudstore"),
            headers=_headers(member_user),
        )
        assert a_get.status_code == status.HTTP_200_OK
        assert a_get.json()["answers"] == {
            "cs-subnet-cidr": "172.16.0.0/16",
            "cs-region": "b-shared-value",
        }

    def test_answers_are_isolated_across_installations(
        self, client, member_user, installation_id, installation_b
    ):
        """Content/answers written under one installation never appear in reads
        scoped to another (design Property 9: Installation data isolation)."""
        installation_b_id = str(installation_b.id)
        assert installation_id != installation_b_id

        # Write under installation A only.
        client.put(
            _answer_path(installation_id, "cloudstore", "cs-region"),
            json={"answer": "written-under-a"},
            headers=_headers(member_user),
        )

        # Installation B has nothing for this slug -> empty map (no leakage).
        b_get = client.get(
            _answers_path(installation_b_id, "cloudstore"),
            headers=_headers(member_user),
        )
        assert b_get.status_code == status.HTTP_200_OK
        assert b_get.json()["answers"] == {}

        # Write the same row under installation B with a different value.
        client.put(
            _answer_path(installation_b_id, "cloudstore", "cs-region"),
            json={"answer": "written-under-b"},
            headers=_headers(member_user),
        )

        # Each installation keeps its own independent value.
        a_get = client.get(
            _answers_path(installation_id, "cloudstore"),
            headers=_headers(member_user),
        )
        assert a_get.status_code == status.HTTP_200_OK
        assert a_get.json()["answers"] == {"cs-region": "written-under-a"}

        b_get2 = client.get(
            _answers_path(installation_b_id, "cloudstore"),
            headers=_headers(member_user),
        )
        assert b_get2.status_code == status.HTTP_200_OK
        assert b_get2.json()["answers"] == {"cs-region": "written-under-b"}

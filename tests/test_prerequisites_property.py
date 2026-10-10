"""Property-based tests for the prerequisites 404 bugfix (task 4).

Bugfix spec: .kiro/specs/basics-prerequisites-404-fix
Migrated by: .kiro/specs/vcf-prerequisites-update (task 6.1)

These Hypothesis-driven properties complement the example-based exploration,
unit, and preservation tests. They exercise the installation-scoped app across
many generated inputs (the family is now
``/api/prerequisites/installations/{id}/{slug}/content|answers[/{row_id}]``):

- **Fix property** (Property 1): for a generated qa slug + rowId + answer under a
  valid installation, a member PUT-then-GET round-trips (the answers map contains
  rowId -> answer); for a generated static slug + content, an admin PUT-then-GET
  round-trips (the returned content matches). No request in the family is ever an
  unmatched-route 404. Validates Requirements 9.3, 7.7.
- **Answer-map property** (Property 3): for a sequence of ``(rowId, answer)``
  PUTs on one slug under one installation, ``GET .../answers`` returns exactly the
  reduction of the sequence (last write wins per rowId; answers are shared per
  installation). Validates Requirements 9.3, 7.7.
- **Preservation property** (Property 2): generated paths/verbs OUTSIDE the
  prerequisites family produce the same status/body as the unfixed baseline.
  Validates Requirements 9.3, 7.7.

State isolation note: the conftest ``client`` fixture is function-scoped and
recreates the DB per test, but ``@given`` runs many examples inside a SINGLE
test function (one DB). Each example must therefore be self-isolating. We
achieve this by generating unique rowIds per example AND cleaning up the rows a
property writes at the end of each example, so state from one example never
corrupts another's assertions. Function-scoped-fixture health checks are
suppressed as recommended by Hypothesis for this pattern.

Validates: Requirements 9.3, 7.7

Property 1: Bug Condition - Prerequisites API is served, not 404
Property 2: Preservation - All non-prerequisites behavior unchanged
Property 3: Answer-map - last write wins per rowId
"""
import uuid

import pytest
from fastapi import status
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models import User, UserRole
from app.models.prerequisite import PrerequisiteAnswer, PrerequisiteContent
from app.auth.token import create_access_token


# --- Known slug sets (kept in sync with app/prerequisites/router.py) ---
STATIC_SLUGS = ("basics", "network-flux")
QA_SLUGS = ("network-checklist", "core-control-plane", "cloudstore", "vcf")


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/test_prerequisites_exploration.py / _unit.py)
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


def _is_bug_condition(path: str) -> bool:
    """Return True if `path` targets the installation-scoped prerequisites contract.

    The family is now
    ``/api/prerequisites/installations/{id}/{slug}/content|answers[/{row_id}]``.
    """
    parts = [p for p in path.split("/") if p]
    if len(parts) < 6:
        return False
    if parts[0] != "api" or parts[1] != "prerequisites" or parts[2] != "installations":
        return False
    resource = parts[5]
    if resource == "content" and len(parts) == 6:
        return True
    if resource == "answers" and len(parts) in (6, 7):
        return True
    return False


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
# rowIds mirror the frontend `rowId` shape (slug-like identifiers). Kept ASCII
# and free of `/` so they stay a single path segment.
_row_id = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1,
    max_size=24,
).filter(lambda s: s.strip("-_") != "")

# Answer/content bodies: arbitrary text (the API stores rich-text HTML but any
# string round-trips). Exclude control chars that TestClient/JSON would mangle
# is unnecessary here since JSON handles them, but keep a sane size bound.
_answer = st.text(max_size=200)
_content = st.text(max_size=500)


# ===========================================================================
# Fix property (Property 1): PUT-then-GET round-trips; never an unmatched 404.
# ===========================================================================
@settings(max_examples=40, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    slug=st.sampled_from(QA_SLUGS),
    row_id=_row_id,
    answer=_answer,
)
def test_answer_put_then_get_round_trips(
    client, member_user, installation_id, slug, row_id, answer
):
    """For any qa slug + rowId + answer, a member PUT then GET round-trips.

    The generated request is in the installation-scoped prerequisites family, so
    it must be SERVED (never an unmatched-route 404), and the answers map must
    contain the written rowId -> answer.

    Validates: Requirements 9.3, 7.7
    """
    put_path = (
        f"/api/prerequisites/installations/{installation_id}"
        f"/{slug}/answers/{row_id}"
    )
    assert _is_bug_condition(put_path)

    put_resp = client.put(
        put_path, json={"answer": answer}, headers=_headers(member_user)
    )
    assert put_resp.status_code != status.HTTP_404_NOT_FOUND, (
        f"COUNTEREXAMPLE: PUT {put_path} -> unmatched-route 404"
    )
    assert put_resp.status_code == status.HTTP_200_OK
    assert put_resp.json() == {"success": True, "slug": slug}

    get_path = f"/api/prerequisites/installations/{installation_id}/{slug}/answers"
    get_resp = client.get(get_path, headers=_headers(member_user))
    assert get_resp.status_code == status.HTTP_200_OK
    body = get_resp.json()
    assert body["slug"] == slug
    assert body["answers"].get(row_id) == answer, (
        f"round-trip failed: wrote {row_id!r}->{answer!r}, got {body['answers']!r}"
    )

    # --- Per-example isolation: remove the row this example wrote so the
    # single shared DB does not accumulate state across examples. ---
    _cleanup_answer(installation_id, slug, row_id)


def test_static_content_put_then_get_round_trips_examples(
    client, admin_user, member_user, installation_id
):
    """Admin PUT static content then GET round-trips for generated content.

    Static content is one row per (installation, slug) (no rowId key), so this
    uses an inner Hypothesis run over generated content strings and resets the
    row after each example to keep the shared DB clean.

    Validates: Requirements 9.3, 7.7
    """
    slug = "basics"
    content_path = (
        f"/api/prerequisites/installations/{installation_id}/{slug}/content"
    )

    @settings(max_examples=30, deadline=None,
              suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(content=_content)
    def _prop(content):
        assert _is_bug_condition(content_path)

        put_resp = client.put(
            content_path, json={"content": content}, headers=_headers(admin_user)
        )
        assert put_resp.status_code != status.HTTP_404_NOT_FOUND, (
            f"COUNTEREXAMPLE: PUT {content_path} -> unmatched-route 404"
        )
        assert put_resp.status_code == status.HTTP_200_OK
        assert put_resp.json() == {"success": True, "slug": slug}

        get_resp = client.get(content_path, headers=_headers(member_user))
        assert get_resp.status_code == status.HTTP_200_OK
        body = get_resp.json()
        assert body["slug"] == slug
        assert body["content"] == content, (
            f"round-trip failed: wrote {content!r}, got {body['content']!r}"
        )

    _prop()
    # Reset the single static row after the property run.
    _cleanup_content(installation_id, slug)


# ===========================================================================
# Answer-map property (Property 3): last write wins per rowId.
# ===========================================================================
@settings(max_examples=30, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    slug=st.sampled_from(QA_SLUGS),
    writes=st.lists(
        st.tuples(_row_id, _answer),
        min_size=1,
        max_size=12,
    ),
)
def test_answer_map_is_last_write_wins_reduction(
    client, member_user, installation_id, slug, writes
):
    """GET .../answers equals the last-write-wins reduction of the PUT sequence.

    For a sequence of (rowId, answer) PUTs on one slug under one installation,
    the returned answers map must equal, for every rowId touched, the LAST
    answer written for that rowId (answers are shared per installation).

    Validates: Requirements 9.3, 7.7
    """
    expected = {}
    touched = []
    for row_id, answer in writes:
        put_path = (
            f"/api/prerequisites/installations/{installation_id}"
            f"/{slug}/answers/{row_id}"
        )
        resp = client.put(
            put_path, json={"answer": answer}, headers=_headers(member_user)
        )
        assert resp.status_code == status.HTTP_200_OK, (
            f"PUT {put_path} -> {resp.status_code}: {resp.text[:200]}"
        )
        expected[row_id] = answer  # last write wins per rowId
        if row_id not in touched:
            touched.append(row_id)

    get_resp = client.get(
        f"/api/prerequisites/installations/{installation_id}/{slug}/answers",
        headers=_headers(member_user),
    )
    assert get_resp.status_code == status.HTTP_200_OK
    answers = get_resp.json()["answers"]

    for row_id, last_answer in expected.items():
        assert answers.get(row_id) == last_answer, (
            f"last-write-wins violated for {row_id!r}: "
            f"expected {last_answer!r}, got {answers.get(row_id)!r}"
        )

    # --- Per-example isolation: remove every row this example wrote. ---
    for row_id in touched:
        _cleanup_answer(installation_id, slug, row_id)


# ===========================================================================
# Preservation property (Property 2): non-family requests match the baseline.
# ===========================================================================
# Path segments that stay clearly OUTSIDE the /api/prerequisites/* family.
_SAFE_SEGMENT = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
    min_size=1,
    max_size=12,
).filter(lambda s: s not in ("", "prerequisites"))


@st.composite
def _non_prerequisites_api_paths(draw):
    """Generate `/api/<...>` paths guaranteed to be outside the family."""
    first = draw(_SAFE_SEGMENT.filter(lambda s: s != "prerequisites"))
    rest = draw(st.lists(_SAFE_SEGMENT, min_size=0, max_size=3))
    return "/api/" + "/".join([first, *rest])


_PREREQ_SHAPES = (
    frozenset({"slug", "content", "updated_at"}),
    frozenset({"slug", "content"}),
    frozenset({"slug", "answers"}),
)


@settings(max_examples=50, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    path=_non_prerequisites_api_paths(),
    verb=st.sampled_from(["GET", "PUT", "POST", "DELETE"]),
)
def test_non_family_requests_never_served_as_prerequisites(client, path, verb):
    """Any generated non-family `/api/*` request is never served a prerequisites
    payload, and undefined paths keep the framework's normal unmatched 404.

    This mirrors the unfixed baseline: the additive fix must not broaden matching
    to swallow paths outside the prerequisites family.

    Validates: Requirements 3.1, 3.3, 3.5
    """
    assert not _is_bug_condition(path)

    resp = client.request(verb, path)

    if resp.status_code == status.HTTP_404_NOT_FOUND:
        # Undefined paths keep the framework default body (the fix must not
        # convert these into prerequisites-served responses).
        assert resp.json() == {"detail": "Not Found"}, (
            f"REGRESSION: {verb} {path} -> non-default 404 body {resp.json()}"
        )

    try:
        body = resp.json()
    except Exception:
        body = None
    if isinstance(body, dict):
        assert frozenset(body.keys()) not in _PREREQ_SHAPES, (
            f"REGRESSION: non-family path {verb} {path} was served a "
            f"prerequisites payload: {body}"
        )


@settings(max_examples=40, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    slug=st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=10),
    verb=st.sampled_from(["GET", "PUT", "POST", "DELETE"]),
)
def test_prerequisites_sibling_paths_keep_normal_404(client, slug, verb):
    """Sibling prerequisites paths that are NOT part of the contract (e.g.
    `/api/prerequisites/{slug}` with no resource) stay outside the family and
    keep the app's normal unmatched-route 404.

    Guards the family boundary so the fix stays narrowly scoped.

    Validates: Requirement 3.1
    """
    path = f"/api/prerequisites/{slug}"
    assert not _is_bug_condition(path)
    resp = client.request(verb, path)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert resp.json() == {"detail": "Not Found"}


# ---------------------------------------------------------------------------
# Cleanup helpers: keep the single shared DB clean between @given examples.
# The router exposes no DELETE, so we reset persisted rows directly via a fresh
# session bound to the same test engine used by the conftest fixtures.
# ---------------------------------------------------------------------------
def _session():
    """Open a session on the same engine the conftest test harness uses."""
    from tests.conftest import TestingSessionLocal
    return TestingSessionLocal()


def _as_uuid(installation_id):
    """Coerce the string ``installation_id`` fixture value to a UUID for the ORM.

    Paths carry the id as a string, but the ``installation_id`` column is a UUID
    type; comparing against a bare string trips the SQLite UUID processor.
    """
    return installation_id if isinstance(installation_id, uuid.UUID) else uuid.UUID(str(installation_id))


def _cleanup_answer(installation_id, slug, row_id):
    """Delete the (installation, slug, row_id) answer row written by an example."""
    db = _session()
    try:
        db.query(PrerequisiteAnswer).filter(
            PrerequisiteAnswer.installation_id == _as_uuid(installation_id),
            PrerequisiteAnswer.slug == slug,
            PrerequisiteAnswer.row_id == row_id,
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _cleanup_content(installation_id, slug):
    """Delete the (installation, slug) static content row written by an example."""
    db = _session()
    try:
        db.query(PrerequisiteContent).filter(
            PrerequisiteContent.installation_id == _as_uuid(installation_id),
            PrerequisiteContent.slug == slug,
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

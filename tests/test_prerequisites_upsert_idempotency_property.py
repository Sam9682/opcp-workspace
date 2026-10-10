"""Property-based test for per-user upsert idempotency.

Feature spec: .kiro/specs/per-user-prerequisites-persistence (task 3.3)
Migrated by: .kiro/specs/vcf-prerequisites-update (task 6.1)

Property 2: Repeated submissions do not duplicate
    For any installation, Q&A slug, and Row_Id, submitting an answer any number
    of times results in exactly one Answer_Record for that
    (installation_id, slug, row_id) triple, holding the most recently submitted
    answer. Answers are shared per installation (no per-user scope).

Validates: Requirements 9.3, 7.7

The property drives PUT
/api/prerequisites/installations/{id}/{slug}/answers/{row_id} through the
FastAPI TestClient with a real Bearer token (a member is authorized to answer),
submitting a non-empty sequence of answers for a single
(installation, slug, row_id). It then asserts, via a direct DB session, that
exactly one PrerequisiteAnswer row exists for the (installation_id, slug,
row_id) triple and that its answer equals the last value submitted.

State isolation note: the conftest ``client`` fixture is function-scoped and
recreates the DB per test, but ``@given`` runs many examples inside a SINGLE
test function (one DB). Each example is made self-isolating by generating a
unique row_id per example and deleting the row it wrote at the end of the
example, so state never leaks across examples. Function-scoped-fixture health
checks are suppressed as recommended by Hypothesis for this pattern.

The row count is inspected through the SAME session the app uses (the
``db_session`` fixture, wired into the app via the conftest ``get_db``
override) rather than a second connection, so there is no SQLite lock
contention and results are deterministic.
"""
import uuid

import pytest
from fastapi import status
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models import User, UserRole
from app.models.prerequisite import PrerequisiteAnswer
from app.auth.token import create_access_token


# Known qa slug set, kept in sync with app/prerequisites/router.py.
QA_SLUGS = ("network-checklist", "core-control-plane", "cloudstore", "vcf")


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/test_prerequisites_property.py / _integration.py)
# ---------------------------------------------------------------------------
@pytest.fixture
def member_user(db_session):
    """Create a member user (allowed to PUT answers)."""
    user = User(
        email="member@prereq.idempotency.test",
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


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
# row_ids mirror the frontend ``rowId`` shape (slug-like identifiers). Kept
# ASCII and free of ``/`` so they stay a single path segment.
_row_id = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1,
    max_size=24,
).filter(lambda s: s.strip("-_") != "")

# Answer bodies: arbitrary text. A non-empty sequence models "any number of
# times" (>= 1) that the same (member, slug, row_id) is submitted.
_answer = st.text(max_size=200)
_answers_seq = st.lists(_answer, min_size=1, max_size=12)


# ---------------------------------------------------------------------------
# DB helpers: use the SAME session the app is wired to (the ``db_session``
# fixture, bound into the app via the conftest ``get_db`` override) so there is
# no second SQLite connection to contend for the file lock.
# ---------------------------------------------------------------------------
def _count_and_last_answer(db, installation_id, slug, row_id):
    """Return (row_count, answer_of_single_row_or_None) for the triple."""
    db.expire_all()  # drop identity-map caching so we observe committed state
    rows = (
        db.query(PrerequisiteAnswer)
        .filter(
            PrerequisiteAnswer.installation_id == installation_id,
            PrerequisiteAnswer.slug == slug,
            PrerequisiteAnswer.row_id == row_id,
        )
        .all()
    )
    return len(rows), (rows[0].answer if len(rows) == 1 else None)


def _cleanup_answer(db, installation_id, slug, row_id):
    db.query(PrerequisiteAnswer).filter(
        PrerequisiteAnswer.installation_id == installation_id,
        PrerequisiteAnswer.slug == slug,
        PrerequisiteAnswer.row_id == row_id,
    ).delete(synchronize_session=False)
    db.commit()


# ===========================================================================
# Property 2: Repeated submissions for one member do not duplicate.
# ===========================================================================
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    slug=st.sampled_from(QA_SLUGS),
    row_id=_row_id,
    answers=_answers_seq,
)
def test_repeated_submissions_do_not_duplicate(
    client, db_session, member_user, installation, slug, row_id, answers
):
    """Feature: vcf-prerequisites-update, migrated Property 2:
    Repeated submissions do not duplicate.

    Submitting an answer for one (installation, slug, row_id) any number of times
    yields exactly one persisted Answer_Record holding the most recent answer.

    Validates: Requirements 9.3, 7.7
    """
    # Namespace the row_id per example to guarantee isolation across the many
    # examples that share this single test's database.
    unique_row_id = f"{row_id}-{uuid.uuid4().hex}"
    installation_id = installation.id

    put_path = (
        f"/api/prerequisites/installations/{installation_id}"
        f"/{slug}/answers/{unique_row_id}"
    )

    # Submit the same triple repeatedly (>= 1 time); each PUT succeeds.
    for answer in answers:
        resp = client.put(
            put_path, json={"answer": answer}, headers=_headers(member_user)
        )
        assert resp.status_code == status.HTTP_200_OK, (
            f"PUT {put_path} -> {resp.status_code}: {resp.text[:200]}"
        )
        assert resp.json() == {"success": True, "slug": slug}

    # Exactly one row for the triple, holding the LAST submitted answer.
    count, stored_answer = _count_and_last_answer(
        db_session, installation_id, slug, unique_row_id
    )
    assert count == 1, (
        f"COUNTEREXAMPLE: {len(answers)} submissions of "
        f"({installation_id}, {slug!r}, {unique_row_id!r}) produced {count} rows "
        f"(expected exactly 1)"
    )
    assert stored_answer == answers[-1], (
        f"COUNTEREXAMPLE: stored answer {stored_answer!r} != "
        f"last submitted {answers[-1]!r}"
    )

    # The GET map likewise reflects a single value for this row_id.
    get_resp = client.get(
        f"/api/prerequisites/installations/{installation_id}/{slug}/answers",
        headers=_headers(member_user),
    )
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["answers"].get(unique_row_id) == answers[-1]

    # --- Per-example isolation: remove the row this example wrote. ---
    _cleanup_answer(db_session, installation_id, slug, unique_row_id)

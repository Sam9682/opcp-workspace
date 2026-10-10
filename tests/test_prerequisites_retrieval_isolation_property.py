"""Property-based test for installation-scoped prerequisites retrieval isolation.

Feature spec: .kiro/specs/per-user-prerequisites-persistence (task 2.2)
Migrated by: .kiro/specs/vcf-prerequisites-update (task 6.1)

The parent spec ``multi-instance-opcp-prerequisites`` re-scoped answers to be
shared per installation (no ``user_id`` scope). The former "retrieval returns
exactly the requesting member's answers" property no longer holds — answers are
not per-user — so it is replaced by its installation-scoped equivalent, matching
design Property 9 (Installation data isolation):

Property 9 (adapted): Retrieval returns exactly the requested installation's
answers for the requested slug.

For any database state containing Answer_Records across arbitrary Installations
and slugs, ``GET /installations/{id}/{slug}/answers`` returns exactly the
Answer_Records for that Installation and slug — no more (other installations'
records excluded, other slugs excluded) and no fewer (empty when that
installation has none for the slug).

Feature: vcf-prerequisites-update, Property 9: Installation data isolation

Validates: Requirements 9.3, 7.7

State isolation note: the conftest ``client`` fixture is function-scoped and
recreates the DB per test, but ``@given`` runs many examples inside a SINGLE
test function (one DB). Each example is therefore made self-isolating: it seeds
a generated set of answer rows directly into the DB, drives the assertions,
then deletes every row it created so state never leaks between examples.
Function-scoped-fixture health checks are suppressed as recommended by
Hypothesis for this pattern.
"""
import uuid

import pytest
from fastapi import status
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models import User, UserRole, Installation
from app.models.prerequisite import PrerequisiteAnswer
from app.auth.token import create_access_token


# Q&A slugs, kept in sync with app/prerequisites/router.py.
QA_SLUGS = ("network-checklist", "core-control-plane", "cloudstore", "vcf")


def _headers(user):
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _session():
    """Open a session on the same engine the conftest test harness uses."""
    from tests.conftest import TestingSessionLocal
    return TestingSessionLocal()


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
# row_ids mirror the frontend `rowId` shape: short slug-like identifiers.
_row_id = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1,
    max_size=24,
).filter(lambda s: s.strip("-_") != "")

_answer = st.text(max_size=200)

# A single seeded record: (installation_index, slug, row_id, answer).
# installation_index selects which of the pre-created installations owns the
# row; it is mapped to a real installation id inside the test. Keeping it an
# index keeps the strategy independent of DB-assigned ids.
_record = st.tuples(
    st.integers(min_value=0, max_value=2),   # one of 3 installations (A, B, C)
    st.sampled_from(QA_SLUGS),
    _row_id,
    _answer,
)


@pytest.fixture
def reader(db_session):
    """Create a single member used to drive the authenticated reads."""
    user = User(
        email="reader@retrieval-isolation.test",
        password_hash="hashed_password",
        first_name="Reader",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def installations(db_session):
    """Create three distinct Installations (A, B, C)."""
    created = []
    for i in range(3):
        inst = Installation(project_name=f"retrieval-isolation-{i}")
        db_session.add(inst)
        created.append(inst)
    db_session.commit()
    for inst in created:
        db_session.refresh(inst)
    return created


# ===========================================================================
# Property 9 (adapted): retrieval returns exactly the requested installation's
# answers for the requested slug.
# ===========================================================================
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    records=st.lists(_record, min_size=0, max_size=15),
    requested_index=st.integers(min_value=0, max_value=2),
    requested_slug=st.sampled_from(QA_SLUGS),
)
def test_retrieval_returns_exactly_requested_installation_answers(
    client, reader, installations, records, requested_index, requested_slug
):
    """Feature: vcf-prerequisites-update, Property 9: Installation data isolation.

    Seed an arbitrary set of answer rows across the installations and slugs, then
    GET one slug under one installation. The returned map must equal the
    last-write-wins reduction of exactly that installation's rows for that slug --
    excluding other installations' rows and other slugs, and empty when that
    installation has none.

    Validates: Requirements 9.3, 7.7
    """
    installation_ids = [inst.id for inst in installations]

    # Deduplicate to the unique (installation_id, slug, row_id) rows that the
    # unique constraint permits, applying last-write-wins per triple to mirror
    # how the upsert path would collapse repeated submissions.
    by_triple: dict[tuple[uuid.UUID, str, str], str] = {}
    for installation_index, slug, row_id, answer in records:
        by_triple[(installation_ids[installation_index], slug, row_id)] = answer

    # Expected map for the requested installation + slug: exactly its rows.
    requested_id = installation_ids[requested_index]
    expected = {
        row_id: answer
        for (iid, slug, row_id), answer in by_triple.items()
        if iid == requested_id and slug == requested_slug
    }

    # --- Seed the generated DB state directly. ---
    db = _session()
    seeded_ids = []
    try:
        for (iid, slug, row_id), answer in by_triple.items():
            row = PrerequisiteAnswer(
                installation_id=iid,
                slug=slug,
                row_id=row_id,
                answer=answer,
            )
            db.add(row)
            db.flush()
            seeded_ids.append(row.id)
        db.commit()
    except Exception:
        db.rollback()
        db.close()
        raise

    try:
        resp = client.get(
            f"/api/prerequisites/installations/{requested_id}/{requested_slug}/answers",
            headers=_headers(reader),
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["slug"] == requested_slug

        got = body["answers"]
        assert got == expected, (
            "COUNTEREXAMPLE: installation isolation violated for "
            f"installation={requested_id} slug={requested_slug!r}: "
            f"expected {expected!r}, got {got!r}"
        )
    finally:
        # --- Per-example isolation: delete every row this example seeded. ---
        cleanup = _session()
        try:
            cleanup.query(PrerequisiteAnswer).filter(
                PrerequisiteAnswer.id.in_(seeded_ids)
            ).delete(synchronize_session=False)
            cleanup.commit()
        finally:
            cleanup.close()
        db.close()

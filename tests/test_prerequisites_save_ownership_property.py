"""Property-based test for installation-scoped answer persistence.

Spec: .kiro/specs/per-user-prerequisites-persistence
Migrated by: .kiro/specs/vcf-prerequisites-update (task 6.1)

The parent spec ``multi-instance-opcp-prerequisites`` re-scoped answers to be
shared per installation (no ``user_id`` scope). The former "saved answers are
owned by the submitting member" property no longer holds — there is no per-user
ownership — so it is replaced by its installation-scoped equivalent, matching
design Property 8 (Installation-scoped answer round-trip):

Property 8 (adapted): Saved answers are persisted under the target installation.

For any Q&A slug, Row_Id, and answer text a member submits via PUT under an
installation, after the upsert the persisted Answer_Record for
(installation_id, slug, row_id) exists and carries the submitted answer text.

Feature: vcf-prerequisites-update, Property 8: Installation-scoped answer round-trip

Validates: Requirements 9.3, 7.7

State isolation note: the conftest ``client`` fixture is function-scoped and
recreates the DB per test, but ``@given`` runs many examples inside a SINGLE
test function (one DB). Each example must therefore be self-isolating. We
generate a fresh installation per example and clean up the answer row(s) the
example wrote at the end, so state from one example never corrupts another's
assertions. Function-scoped-fixture health checks are suppressed as recommended
by Hypothesis for this pattern.
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


def _make_member():
    """Create a fresh member (unique email) and return the User instance.

    Uses a standalone session on the shared test engine so the member is
    persisted independently of any per-example cleanup.
    """
    db = _session()
    try:
        user = User(
            email=f"member-{uuid.uuid4().hex}@prereq.test",
            password_hash="hashed_password",
            first_name="Member",
            last_name="User",
            role=UserRole.MEMBER,
            is_email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _make_installation():
    """Create a fresh Installation and return its id (standalone session)."""
    db = _session()
    try:
        inst = Installation(project_name=f"inst-{uuid.uuid4().hex}")
        db.add(inst)
        db.commit()
        db.refresh(inst)
        return inst.id
    finally:
        db.close()


# rowIds mirror the frontend `rowId` shape (slug-like identifiers). Kept ASCII
# and free of `/` so they stay a single path segment.
_row_id = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1,
    max_size=24,
).filter(lambda s: s.strip("-_") != "")

# Answer bodies: arbitrary text (the API stores rich-text HTML but any string
# round-trips through JSON).
_answer = st.text(max_size=200)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    slug=st.sampled_from(QA_SLUGS),
    row_id=_row_id,
    answer=_answer,
)
def test_saved_answer_is_persisted_under_installation(client, slug, row_id, answer):
    """A member PUT persists an Answer_Record under the target installation.

    For any qa slug + rowId + answer, after the PUT upsert the persisted row for
    (installation_id, slug, row_id) exists and holds the submitted answer text.

    Validates: Requirements 9.3, 7.7
    """
    member = _make_member()
    installation_id = _make_installation()

    put_path = (
        f"/api/prerequisites/installations/{installation_id}"
        f"/{slug}/answers/{row_id}"
    )
    put_resp = client.put(
        put_path, json={"answer": answer}, headers=_headers(member)
    )
    assert put_resp.status_code == status.HTTP_200_OK, (
        f"PUT {put_path} -> {put_resp.status_code}: {put_resp.text[:200]}"
    )
    assert put_resp.json() == {"success": True, "slug": slug}

    # Verify persistence directly against the persistence layer: exactly one row
    # for (installation, slug, row_id), carrying the submitted answer text.
    db = _session()
    try:
        rows = (
            db.query(PrerequisiteAnswer)
            .filter(
                PrerequisiteAnswer.installation_id == installation_id,
                PrerequisiteAnswer.slug == slug,
                PrerequisiteAnswer.row_id == row_id,
            )
            .all()
        )
        assert len(rows) == 1, (
            f"expected exactly one Answer_Record for "
            f"({installation_id}, {slug!r}, {row_id!r}), got {len(rows)}"
        )
        row = rows[0]
        assert row.installation_id == installation_id, (
            f"scoping violated: row.installation_id={row.installation_id!r} "
            f"!= target installation {installation_id!r}"
        )
        assert row.answer == answer, (
            f"answer text not persisted: wrote {answer!r}, stored {row.answer!r}"
        )
    finally:
        db.close()

    # --- Per-example isolation: remove the row this example wrote so the single
    # shared DB does not accumulate state across examples. ---
    db = _session()
    try:
        db.query(PrerequisiteAnswer).filter(
            PrerequisiteAnswer.installation_id == installation_id,
        ).delete(synchronize_session=False)
        inst = (
            db.query(Installation).filter(Installation.id == installation_id).first()
        )
        if inst is not None:
            db.delete(inst)
        db.commit()
    finally:
        db.close()

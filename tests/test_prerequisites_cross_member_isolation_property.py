"""Property-based test for cross-installation isolation on save.

Spec: .kiro/specs/per-user-prerequisites-persistence
Migrated by: .kiro/specs/vcf-prerequisites-update (task 6.1)

The parent spec ``multi-instance-opcp-prerequisites`` re-scoped answers to be
shared per installation (no ``user_id`` scope, last-write-wins). Per-user answer
isolation no longer exists, so the former "one member's save never alters
another member's answer" property is replaced by its installation-scoped
equivalent, matching design Property 9 (Installation data isolation):

Property 9 (adapted): One installation's save never alters another
installation's answer.

For any two distinct Installations sharing the same Q&A slug and Row_Id, when a
member writes an answer under one Installation via PUT, the OTHER Installation's
Answer_Record for that same slug and Row_Id is left unchanged.

Feature: vcf-prerequisites-update, Property 9: Installation data isolation

Validates: Requirements 9.3, 7.7

State isolation note: the conftest ``client`` fixture is function-scoped and
recreates the DB per test, but ``@given`` runs many examples inside a SINGLE
test function (one DB). Each example must therefore be self-isolating. We
generate two fresh installations per example and clean up the answer rows the
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
    """Create a fresh member (unique email) and return the User instance."""
    db = _session()
    try:
        user = User(
            email=f"member-{uuid.uuid4().hex}@prereq.isolation.test",
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


def _fetch_answer(installation_id, slug, row_id):
    """Return the single stored answer for (installation_id, slug, row_id) or None."""
    db = _session()
    try:
        row = (
            db.query(PrerequisiteAnswer)
            .filter(
                PrerequisiteAnswer.installation_id == installation_id,
                PrerequisiteAnswer.slug == slug,
                PrerequisiteAnswer.row_id == row_id,
            )
            .one_or_none()
        )
        return None if row is None else row.answer
    finally:
        db.close()


def _cleanup(*installation_ids):
    db = _session()
    try:
        db.query(PrerequisiteAnswer).filter(
            PrerequisiteAnswer.installation_id.in_(list(installation_ids)),
        ).delete(synchronize_session=False)
        for inst_id in installation_ids:
            inst = (
                db.query(Installation).filter(Installation.id == inst_id).first()
            )
            if inst is not None:
                db.delete(inst)
        db.commit()
    finally:
        db.close()


# rowIds mirror the frontend `rowId` shape (slug-like identifiers). Kept ASCII
# and free of `/` so they stay a single path segment. Small to bound runtime.
_row_id = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1,
    max_size=24,
).filter(lambda s: s.strip("-_") != "")

# Answer bodies: arbitrary text (max_size kept small to bound runtime).
_answer = st.text(max_size=200)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    slug=st.sampled_from(QA_SLUGS),
    row_id=_row_id,
    other_answer=_answer,
    saving_answer=_answer,
)
def test_save_does_not_alter_other_installations_answer(
    client, slug, row_id, other_answer, saving_answer
):
    """A save under one installation never alters another installation's answer.

    Two distinct installations share the same slug + rowId. A member first
    persists an answer under the "other" installation. Then the member
    creates/updates an answer for the same slug + rowId under the "saving"
    installation. Afterwards the other installation's stored Answer_Record for
    that slug + rowId is unchanged.

    Validates: Requirements 9.3, 7.7
    """
    member = _make_member()
    other_installation = _make_installation()
    saving_installation = _make_installation()
    assert other_installation != saving_installation

    def _put_path(installation_id):
        return (
            f"/api/prerequisites/installations/{installation_id}"
            f"/{slug}/answers/{row_id}"
        )

    # Establish the "other" installation's answer for the shared triple.
    other_put = client.put(
        _put_path(other_installation),
        json={"answer": other_answer},
        headers=_headers(member),
    )
    assert other_put.status_code == status.HTTP_200_OK, (
        f"PUT (other) -> {other_put.status_code}: {other_put.text[:200]}"
    )

    # Snapshot the other installation's persisted answer before the save.
    other_before = _fetch_answer(other_installation, slug, row_id)
    assert other_before == other_answer

    # Create/update the answer for the same triple under the saving installation.
    saving_put = client.put(
        _put_path(saving_installation),
        json={"answer": saving_answer},
        headers=_headers(member),
    )
    assert saving_put.status_code == status.HTTP_200_OK, (
        f"PUT (saving) -> {saving_put.status_code}: {saving_put.text[:200]}"
    )
    assert saving_put.json() == {"success": True, "slug": slug}

    # The other installation's Answer_Record for the same slug + rowId is untouched.
    other_after = _fetch_answer(other_installation, slug, row_id)
    assert other_after == other_before, (
        f"COUNTEREXAMPLE: save under installation {saving_installation} altered "
        f"installation {other_installation}'s answer for ({slug!r}, {row_id!r}): "
        f"before={other_before!r} after={other_after!r}"
    )

    # The saving installation's own record reflects what was submitted.
    saving_stored = _fetch_answer(saving_installation, slug, row_id)
    assert saving_stored == saving_answer, (
        f"saving installation's own answer not persisted: wrote {saving_answer!r}, "
        f"stored {saving_stored!r}"
    )

    # --- Per-example isolation: remove rows this example wrote. ---
    _cleanup(other_installation, saving_installation)

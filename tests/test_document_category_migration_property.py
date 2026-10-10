"""Property test for the document-category remap migration.

Feature: admin-document-upload-categories

Covers:
- Property 7: the ``remap_document_categories`` migration remaps every existing
  row to ``documents`` and the API returns each such document with category
  ``documents`` (Requirements 6.1, 6.2, 6.3).

The ``category`` column is a non-native ``SQLEnum`` (stored as VARCHAR holding
the enum *member name*). Pre-migration rows are seeded with the legacy
member-name forms (``STATUTES``, ``MINUTES``, ``FINANCIAL_REPORTS``, ``OTHER``)
directly via raw SQL, since those values are no longer part of the enum and
cannot be inserted through the ORM. The migration's real ``upgrade()`` is then
invoked under an Alembic ``Operations`` context bound to the test connection,
so ``op.get_bind()`` and ``sa.text(...)`` execute exactly as in production.

State isolation note: ``@given`` runs many examples inside one test function
(one DB), so each example resets the ``documents`` table first.
"""

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import status
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.auth.token import create_access_token
from app.models import Document, User
from app.models.document import DocumentCategory

from tests.conftest import TestingSessionLocal, engine


# ---------------------------------------------------------------------------
# Load the migration module by file path (its filename is not importable as a
# normal dotted module).
# ---------------------------------------------------------------------------
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260928_0000_remap_document_categories_remap_document_categories.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "remap_document_categories_migration", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration()


# The four legacy category member-name forms that pre-migration rows may hold.
_LEGACY_CATEGORIES = ["STATUTES", "MINUTES", "FINANCIAL_REPORTS", "OTHER"]
# Access levels are stored as their member names by the non-native enum.
_ACCESS_LEVELS = ["PUBLIC", "MEMBERS", "ADMINISTRATORS"]


@pytest.fixture
def admin_user(db_session):
    user = User(
        email="admin@test.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role="administrator",
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _headers(user) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _reset_documents() -> None:
    db = TestingSessionLocal()
    try:
        db.query(Document).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _run_upgrade() -> None:
    """Invoke the migration's real ``upgrade()`` against the test engine.

    Binds a live connection into an Alembic ``Operations`` context so that
    ``op.get_bind()`` inside ``upgrade()`` returns this connection.
    """
    with engine.begin() as connection:
        ctx = MigrationContext.configure(connection)
        with Operations.context(ctx):
            MIGRATION.upgrade()


# A generated collection of pre-migration rows: each item is (legacy_category,
# access_level) chosen from the legacy/enum member-name sets.
_row_spec = st.tuples(
    st.sampled_from(_LEGACY_CATEGORIES),
    st.sampled_from(_ACCESS_LEVELS),
)


@pytest.mark.property
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(specs=st.lists(_row_spec, min_size=0, max_size=8))
def test_property7_migration_remaps_all_rows_to_documents(
    client, admin_user, specs
):
    """Feature: admin-document-upload-categories, Property 7: Migration remaps
    all rows to ``documents``.

    For an arbitrary set of pre-migration rows with legacy categories, after
    ``upgrade()`` every row's category equals ``documents`` and the API returns
    each such document as ``documents``.

    Validates: Requirements 6.1, 6.2, 6.3
    """
    _reset_documents()

    # Seed pre-migration rows with legacy category member-names via raw SQL,
    # bypassing the ORM enum (which no longer knows the legacy values). All are
    # inserted at PUBLIC-accessible or higher; the admin principal sees them all.
    db = TestingSessionLocal()
    try:
        for i, (legacy_category, access_level) in enumerate(specs):
            db.execute(
                Document.__table__.insert().values(
                    id=uuid.uuid4(),
                    filename=f"legacy_{i}_{uuid.uuid4().hex}.pdf",
                    original_name=f"Legacy {i}.pdf",
                    mime_type="application/pdf",
                    size=1024,
                    category=legacy_category,          # raw legacy member name
                    access_level=access_level,
                    uploaded_by=admin_user.id,
                    download_count=0,
                    created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                    updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                )
            )
        db.commit()
    finally:
        db.close()

    # Run the real migration upgrade.
    _run_upgrade()

    # Every stored row now holds the DOCUMENTS member name.
    db = TestingSessionLocal()
    try:
        from sqlalchemy import text

        raw_categories = [
            r[0] for r in db.execute(text("SELECT category FROM documents")).fetchall()
        ]
        assert all(c == "DOCUMENTS" for c in raw_categories)
        assert len(raw_categories) == len(specs)

        # The ORM deserializes each row as DocumentCategory.DOCUMENTS.
        for doc in db.query(Document).all():
            assert doc.category is DocumentCategory.DOCUMENTS
    finally:
        db.close()

    # The API returns each document with category "documents" (admin sees all).
    response = client.get("/api/documents", headers=_headers(admin_user))
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["total"] == len(specs)
    assert all(
        doc["category"] == DocumentCategory.DOCUMENTS.value
        for doc in body["documents"]
    )

    _reset_documents()

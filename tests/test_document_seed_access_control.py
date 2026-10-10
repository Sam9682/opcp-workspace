"""Access-control integration tests for seeded documents.

Feature: docs-auto-seed-and-documents-page
Task 4 — Validates Requirements 5.2, 5.3:

  - 5.2: A ``members``-level seeded document is visible to a Registered_User
         (a MEMBER) via ``GET /api/documents``.
  - 5.3: An Anonymous_User is denied download of a seeded document (403).

These tests exercise the real document API through the ``client`` fixture
(which overrides ``get_db`` with the in-memory ``db_session``). The seeded
document is produced by the actual seeding worker ``_seed_single_file`` so the
Document row (access_level=MEMBERS, admin-owned) and its Stored_File are real.

Storage is isolated by monkeypatching the module-level
``storage_service.upload_dir`` singleton at a ``tmp_path`` before seeding; the
document router imports that same singleton, so the file resolves globally for
the member download path.
"""
from pathlib import Path

import pytest

from app.config import settings as app_settings
from app.models.document import Document, AccessLevel
from app.models.user import User, UserRole
from app.services.document_seed_service import _seed_single_file
from app.services.storage_service import storage_service


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_admin(db, email="seed-admin@example.com"):
    """Create and persist an ADMINISTRATOR user (the Seeding_Admin).

    A distinct email is used so this does not collide with the default admin
    (``admin@opcp-psmc.com``) that the application lifespan creates on the same
    in-memory session when the TestClient starts.
    """
    admin = User(
        email=email,
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture()
def isolated_storage(tmp_path, monkeypatch):
    """Point the module-level storage_service singleton at a temp uploads dir.

    The document router uses this same singleton, so seeding and download both
    resolve against the isolated directory.
    """
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(storage_service, "upload_dir", uploads)
    monkeypatch.setattr(app_settings, "UPLOAD_DIR", str(uploads))
    return uploads


@pytest.fixture()
def seeded_members_document(client, db_session, isolated_storage, tmp_path, monkeypatch):
    """Seed one members-level document into ``db_session`` and return it.

    Depends on ``client`` so the application lifespan (which creates the default
    admin and seeds the real ``docs/`` folder) has already run before this
    fixture seeds its own document. Uses the real ``_seed_single_file`` worker
    so the Document is created with ``access_level=MEMBERS`` and ``uploaded_by``
    set to a real ADMINISTRATOR, backed by an actual Stored_File on disk.

    ``isolated_storage`` repoints the storage singleton at a temp uploads dir
    *after* the lifespan ran, so this document's bytes resolve there.
    """
    # Point DOCS_SEED_DIR at a temp docs folder for completeness (patch requirement).
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(app_settings, "DOCS_SEED_DIR", str(docs_dir))

    # Use a unique original_name so this document is unambiguous even when the
    # lifespan has seeded the real docs/ folder into the shared test database.
    original_name = "statuts-PSMC-seed-test.pdf"
    admin = _make_admin(db_session)

    # Create a real source file inside the docs dir and seed it.
    source = docs_dir / original_name
    source.write_bytes(b"%PDF-1.4 seeded members document content")

    _seed_single_file(db_session, admin, source)
    db_session.commit()

    document = (
        db_session.query(Document)
        .filter(Document.original_name == original_name)
        .first()
    )
    assert document is not None
    # Precondition: seeding produced a members-level, admin-owned record.
    assert document.access_level == AccessLevel.MEMBERS
    assert document.uploaded_by == admin.id
    # The Stored_File must exist on disk for the download path to serve it.
    assert storage_service.get_file_path(document.filename) is not None
    return document


# ---------------------------------------------------------------------------
# Requirement 5.2 — members document visible to a Registered_User
# ---------------------------------------------------------------------------

def test_members_document_visible_to_registered_user(
    client, auth_headers, seeded_members_document
):
    """A MEMBER sees the seeded members-level document via GET /api/documents.

    Validates: Requirement 5.2
    """
    response = client.get("/api/documents", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    returned_ids = {doc["id"] for doc in body["documents"]}
    assert str(seeded_members_document.id) in returned_ids

    # The returned record carries the expected metadata.
    seeded = next(
        doc for doc in body["documents"]
        if doc["id"] == str(seeded_members_document.id)
    )
    assert seeded["original_name"] == seeded_members_document.original_name
    assert seeded["access_level"] == AccessLevel.MEMBERS.value


def test_members_document_hidden_from_anonymous_list(
    client, seeded_members_document
):
    """An Anonymous_User's document list excludes the members-level document.

    Validates: Requirement 5.2 (only registered users see members documents;
    anonymous listing returns public documents only).
    """
    response = client.get("/api/documents")

    assert response.status_code == 200
    body = response.json()
    returned_ids = {doc["id"] for doc in body["documents"]}
    assert str(seeded_members_document.id) not in returned_ids


# ---------------------------------------------------------------------------
# Requirement 5.3 — anonymous download denied; member download allowed
# ---------------------------------------------------------------------------

def test_anonymous_download_of_members_document_denied(
    client, seeded_members_document
):
    """An Anonymous_User is denied download of a seeded members document (403).

    Validates: Requirement 5.3
    """
    response = client.get(f"/api/documents/{seeded_members_document.id}/download")

    assert response.status_code == 403


def test_member_can_download_members_document(
    client, auth_headers, seeded_members_document
):
    """A Registered_User (MEMBER) can download the seeded members document.

    Confirms the members doc is downloadable by a registered user (Req 5.3
    access model) and the Stored_File is served.
    """
    response = client.get(
        f"/api/documents/{seeded_members_document.id}/download",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 seeded members document content"

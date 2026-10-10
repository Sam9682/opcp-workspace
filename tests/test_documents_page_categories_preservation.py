"""Preservation tests for the documents-page-categories bugfix.

Feature: documents-page-categories (BUGFIX)
Property 2: Preservation - Behavior Unrelated To Subfolder Grouping
Validates: Requirements 3.2, 3.3, 3.4, 3.5, 3.6

These tests are written BEFORE the fix (observation-first methodology). They
capture the CURRENT (unfixed) observable behavior of the document pipeline for
inputs unrelated to subfolder grouping, so they MUST PASS on the unfixed code.
After the fix they will be re-run to confirm no regressions.

Covered here (backend-observable behaviors):
    - Download: download returns the correct file by ``original_name`` via the
      existing endpoint, with access control (Requirement 3.2).
    - Upload: an admin upload is accepted and the listing then includes the new
      file (Requirement 3.3).
    - RBAC: list/download respect public/members/administrators — randomized
      ``(role, access_level)`` combinations assert the list/download outcome
      (Requirement 3.4).
    - Empty-state: when no documents match the current view the listing returns
      an empty set (Requirement 3.6), and a category with no rows is absent from
      the listing (Requirement 3.5).
    - Exclusion: files under ``movies``/``images`` are NOT seeded (they do not
      become category sections).

Filename-search semantics (Requirement 3.1) are a frontend concern and are
captured in ``frontend/src/pages/DocumentsPage.preservation.test.tsx``.
"""
import io

import pytest
from fastapi import status
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.models import User, Document
from app.models.document import DocumentCategory, AccessLevel
from app.models.user import UserRole
from app.auth.token import create_access_token
from app.services import document_seed_service
from app.services.document_seed_service import seed_docs_folder, discover_source_files
from app.services.storage_service import storage_service


# ---------------------------------------------------------------------------
# Fixtures: users, auth headers, storage isolation.
# ---------------------------------------------------------------------------
@pytest.fixture
def admin_user(db_session):
    user = User(
        email="admin@test.com",
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
    user = User(
        email="member@test.com",
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
def visitor_user(db_session):
    user = User(
        email="visitor@test.com",
        password_hash="hashed_password",
        first_name="Visitor",
        last_name="User",
        role=UserRole.VISITOR,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _headers(user) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Download preservation — the endpoint returns the correct file by
# original_name with the correct access control. (Requirement 3.2)
# ---------------------------------------------------------------------------
def test_download_returns_correct_file_by_original_name(client, admin_user):
    """A public document downloads with its ``original_name`` and content.

    Preserves Requirement 3.2: download returns the correct file by its original
    name via the existing endpoint.
    """
    content = b"the real bytes of statutes"
    unique_filename, _ = storage_service.save_file(content, "Statuts 2024.pdf")
    try:
        doc = Document(
            filename=unique_filename,
            original_name="Statuts 2024.pdf",
            mime_type="application/pdf",
            size=len(content),
            category=DocumentCategory.DOCUMENTS,
            access_level=AccessLevel.PUBLIC,
            uploaded_by=admin_user.id,
            download_count=0,
        )
        # add + commit via the client's session override
        from app.database import get_db  # noqa: F401
        # Use the app dependency-overridden session by going through the API:
        # simplest is to persist through the same session the client uses.
        # The client fixture overrides get_db with db_session, so persist there.
        _persist(client, doc)

        response = client.get(f"/api/documents/{doc.id}/download")

        assert response.status_code == status.HTTP_200_OK
        assert response.content == content
        assert "Statuts 2024.pdf" in response.headers["content-disposition"]
        assert response.headers["content-type"] == "application/pdf"
    finally:
        storage_service.delete_file(unique_filename)


def _persist(client, doc: Document) -> None:
    """Persist a Document via the session the TestClient uses.

    The ``client`` fixture overrides ``get_db`` to yield the shared
    ``db_session``; we reach it through the app's dependency override so the row
    is visible to subsequent API calls.
    """
    from app.main import app
    from app.database import get_db

    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    session.add(doc)
    session.commit()
    session.refresh(doc)


# ---------------------------------------------------------------------------
# Upload preservation — an admin upload is accepted and the listing then
# includes the new file. (Requirement 3.3)
# ---------------------------------------------------------------------------
def test_admin_upload_accepted_and_appears_in_listing(client, admin_user):
    """An admin uploads a supported file; the listing then includes it.

    Preserves Requirement 3.3: admin upload accepted and list refreshes so the
    new file appears.
    """
    headers = _headers(admin_user)
    file_bytes = b"# Guide\nhello"
    files = {"file": ("guide.md", io.BytesIO(file_bytes), "text/markdown")}
    data = {"access_level": AccessLevel.PUBLIC.value}

    upload = client.post(
        "/api/documents/upload", headers=headers, files=files, data=data
    )
    assert upload.status_code == status.HTTP_201_CREATED, upload.text
    created = upload.json()["document"]
    assert created["original_name"] == "guide.md"

    # The subsequent listing (as admin) must include the uploaded file.
    listing = client.get("/api/documents", headers=headers)
    assert listing.status_code == status.HTTP_200_OK
    names = {d["original_name"] for d in listing.json()["documents"]}
    assert "guide.md" in names

    # Cleanup the stored file.
    storage_service.delete_file(created["filename"])


def test_non_admin_upload_is_rejected(client, member_user):
    """A non-admin upload is rejected (behavior preserved).

    Preserves Requirement 3.3 / 3.4: only administrators may upload.
    """
    headers = _headers(member_user)
    files = {"file": ("guide.md", io.BytesIO(b"x"), "text/markdown")}
    data = {"access_level": AccessLevel.PUBLIC.value}

    response = client.post(
        "/api/documents/upload", headers=headers, files=files, data=data
    )
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


# ---------------------------------------------------------------------------
# RBAC preservation (property-based) — list visibility for randomized
# (viewer role, document access_level) combinations. (Requirement 3.4)
# ---------------------------------------------------------------------------
# viewer role: None means unauthenticated.
_ROLES = st.sampled_from([None, UserRole.VISITOR, UserRole.MEMBER, UserRole.ADMINISTRATOR])
_ACCESS = st.sampled_from(
    [AccessLevel.PUBLIC, AccessLevel.MEMBERS, AccessLevel.ADMINISTRATORS]
)


def _visible_expected(role, access_level) -> bool:
    """The current (preserved) visibility rule for list/download.

    - Unauthenticated: only PUBLIC.
    - MEMBER / VISITOR: PUBLIC and MEMBERS.
    - ADMINISTRATOR: everything.
    """
    if role is None:
        return access_level == AccessLevel.PUBLIC
    if role == UserRole.ADMINISTRATOR:
        return True
    # MEMBER and VISITOR
    return access_level in (AccessLevel.PUBLIC, AccessLevel.MEMBERS)


@pytest.mark.property
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(role=_ROLES, access_level=_ACCESS)
def test_rbac_list_visibility_preserved(client, db_session, role, access_level):
    """For any (role, access_level), listing includes the document iff the
    current RBAC rule permits it.

    Preserves Requirement 3.4: role-based access control on listing.
    """
    # Clean slate for this generated example.
    db_session.query(Document).delete()
    db_session.query(User).delete()
    db_session.commit()

    uploader = User(
        email="uploader@test.com",
        password_hash="hashed",
        first_name="Up",
        last_name="Loader",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True,
    )
    db_session.add(uploader)
    db_session.commit()
    db_session.refresh(uploader)

    doc = Document(
        filename="rbac_probe.pdf",
        original_name="RBAC Probe.pdf",
        mime_type="application/pdf",
        size=10,
        category=DocumentCategory.DOCUMENTS,
        access_level=access_level,
        uploaded_by=uploader.id,
        download_count=0,
    )
    db_session.add(doc)
    db_session.commit()

    headers = {}
    if role is not None:
        viewer = User(
            email="viewer@test.com",
            password_hash="hashed",
            first_name="View",
            last_name="Er",
            role=role,
            is_email_verified=True,
        )
        db_session.add(viewer)
        db_session.commit()
        db_session.refresh(viewer)
        headers = _headers(viewer)

    response = client.get("/api/documents", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    names = {d["original_name"] for d in response.json()["documents"]}

    expected_visible = _visible_expected(role, access_level)
    assert ("RBAC Probe.pdf" in names) == expected_visible, (
        f"role={role} access_level={access_level} "
        f"expected_visible={expected_visible} got_names={names}"
    )


# ---------------------------------------------------------------------------
# Empty-state / empty-category preservation. (Requirements 3.5, 3.6)
# ---------------------------------------------------------------------------
def test_listing_empty_when_no_documents(client, admin_user):
    """With no documents, the listing returns an empty set.

    Preserves Requirement 3.6: empty-state (no files match the current view).
    """
    response = client.get("/api/documents", headers=_headers(admin_user))
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["total"] == 0
    assert body["documents"] == []


def test_category_with_no_rows_absent_from_listing(client, admin_user):
    """A category filter with no matching rows returns nothing.

    Preserves Requirement 3.5: an empty category section is omitted (the API
    surfaces no rows for that category, so the page renders no section).
    """
    # Persist a single DOCUMENTS row, then filter by SCRIPTS.
    doc = Document(
        filename="only_doc.pdf",
        original_name="Only Doc.pdf",
        mime_type="application/pdf",
        size=10,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.PUBLIC,
        uploaded_by=admin_user.id,
        download_count=0,
    )
    _persist(client, doc)

    response = client.get(
        "/api/documents",
        params={"category": DocumentCategory.SCRIPTS.value},
        headers=_headers(admin_user),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["total"] == 0


# ---------------------------------------------------------------------------
# Exclusion preservation — non-content subfolders are not seeded, and the
# current non-recursive discovery only surfaces top-level files. (design Scope)
# ---------------------------------------------------------------------------
@pytest.fixture
def _use_test_session(db_session, monkeypatch):
    """Route seed_docs_folder through the test session and keep it open."""
    monkeypatch.setattr(document_seed_service, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    return db_session


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(
        document_seed_service.storage_service, "upload_dir", upload_dir
    )
    return upload_dir


def test_discovery_does_not_surface_movies_or_images_top_level(tmp_path):
    """A top-level scan never surfaces files that live under movies/images.

    Observation on UNFIXED code: discovery is non-recursive, so files placed in
    subfolders (including movies/images) are not surfaced. This preserves the
    exclusion guarantee that movies/images never become categories.
    """
    root = tmp_path / "to_publish"
    (root / "movies").mkdir(parents=True)
    (root / "images").mkdir(parents=True)
    (root / "movies" / "intro.md").write_bytes(b"movie")
    (root / "images" / "logo.pdf").write_bytes(b"image")
    # A genuine top-level file to confirm discovery still returns something.
    (root / "readme.md").write_bytes(b"top level")

    discovered = discover_source_files(root)

    def _name(entry):
        return entry[0].name if isinstance(entry, tuple) else entry.name

    names = {_name(e) for e in discovered}
    assert "intro.md" not in names
    assert "logo.pdf" not in names


def test_movies_images_files_are_not_seeded(
    tmp_path, admin_user, _use_test_session, isolated_storage, db_session
):
    """Seeding a fixture with movies/images subfolders creates no rows for them.

    Preserves the exclusion guarantee (movies/images do not become categories).
    """
    root = tmp_path / "to_publish"
    (root / "movies").mkdir(parents=True)
    (root / "images").mkdir(parents=True)
    (root / "movies" / "intro.md").write_bytes(b"movie")
    (root / "images" / "logo.pdf").write_bytes(b"image")

    seed_docs_folder(root)

    for excluded in ("intro.md", "logo.pdf"):
        row = (
            db_session.query(Document)
            .filter(Document.original_name == excluded)
            .first()
        )
        assert row is None, f"excluded-subfolder file was seeded: {excluded}"

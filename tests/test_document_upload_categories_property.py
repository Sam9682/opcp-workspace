"""Property and integration tests for the extension-derived upload endpoint.

Feature: admin-document-upload-categories

Covers:
- Property 3 (endpoint portion): an upload with an unmapped extension yields an
  error response and creates no document row (Requirements 2.4, 4.3).
- Property 5: uploads are administrator-only (Requirements 3.4, 3.5).
- Property 6: role-based listing filter returns exactly the permitted
  access-level set for each principal (Requirement 5.3).

State isolation note: the conftest ``client`` fixture is function-scoped and
recreates the DB per test, but ``@given`` runs many examples inside a SINGLE
test function (one DB). Each example therefore resets the ``documents`` table so
that examples don't accumulate rows across iterations.
"""

import io
import uuid

import pytest
from fastapi import status
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models import User, Document
from app.models.document import DocumentCategory, AccessLevel, CATEGORY_MAPPING
from app.auth.token import create_access_token


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
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


@pytest.fixture
def member_user(db_session):
    user = User(
        email="member@test.com",
        password_hash="hashed_password",
        first_name="Member",
        last_name="User",
        role="member",
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
        role="visitor",
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
# Table reset helper (see state-isolation note above)
# ---------------------------------------------------------------------------
def _reset_documents() -> None:
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        db.query(Document).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _document_count() -> int:
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    try:
        return db.query(Document).count()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3.1 Property 3 (endpoint): unmapped extensions are rejected, no row created
# ---------------------------------------------------------------------------
# Generate a base name plus an extension guaranteed NOT to be in CATEGORY_MAPPING
# (including the empty-extension case).
_unmapped_ext = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=0, max_size=6
).filter(lambda e: e.lower() not in CATEGORY_MAPPING)
_base_name = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_-", min_size=1, max_size=12
)


@pytest.mark.property
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(base=_base_name, ext=_unmapped_ext)
def test_property3_unmapped_extension_upload_rejected(
    client, admin_user, base, ext
):
    """Feature: admin-document-upload-categories, Property 3: Unknown extensions
    are rejected (endpoint portion).

    An admin upload whose extension is not in CATEGORY_MAPPING is rejected with
    an error response and creates no document row.

    Validates: Requirements 2.4, 4.3
    """
    _reset_documents()

    filename = f"{base}.{ext}" if ext else base
    response = client.post(
        "/api/documents/upload",
        files={"file": (filename, io.BytesIO(b"payload"), "application/octet-stream")},
        data={"access_level": AccessLevel.PUBLIC.value},
        headers=_headers(admin_user),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    body = response.json()
    assert body["error"]["code"] == "INVALID_FILE_TYPE"
    # No row persisted for a rejected upload.
    assert _document_count() == 0


# ---------------------------------------------------------------------------
# 3.2 Property 5 (integration): upload is administrator-only
# ---------------------------------------------------------------------------
def test_property5_non_admin_upload_forbidden_no_row(
    client, member_user, db_session
):
    """Feature: admin-document-upload-categories, Property 5: Upload is
    administrator-only.

    A non-admin POST to the upload endpoint is rejected with an authorization
    error and creates no document row.

    Validates: Requirements 3.4, 3.5
    """
    response = client.post(
        "/api/documents/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        data={"access_level": AccessLevel.PUBLIC.value},
        headers=_headers(member_user),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error"]["code"] == "ADMIN_ACCESS_REQUIRED"
    assert db_session.query(Document).count() == 0


def test_property5_admin_upload_succeeds(client, admin_user, db_session):
    """Feature: admin-document-upload-categories, Property 5: an admin upload
    succeeds and creates exactly one row.

    Validates: Requirements 3.4, 3.5
    """
    response = client.post(
        "/api/documents/upload",
        files={"file": ("guide.md", io.BytesIO(b"# Guide"), "text/markdown")},
        data={"access_level": AccessLevel.PUBLIC.value},
        headers=_headers(admin_user),
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["success"] is True
    assert data["document"]["category"] == DocumentCategory.DOCUMENTS.value
    assert db_session.query(Document).count() == 1


# ---------------------------------------------------------------------------
# 3.3 Property 6: role-based listing filter
# ---------------------------------------------------------------------------
_ACCESS_LEVELS = [
    AccessLevel.PUBLIC,
    AccessLevel.MEMBERS,
    AccessLevel.ADMINISTRATORS,
]
_CATEGORIES = [
    DocumentCategory.DOCUMENTS,
    DocumentCategory.SCRIPTS,
    DocumentCategory.LINKS,
]

# A generated collection of stored documents: each item is (access_level_index,
# category_index).
_doc_spec = st.tuples(
    st.integers(min_value=0, max_value=2),
    st.integers(min_value=0, max_value=2),
)


def _permitted_levels(principal: str) -> set:
    """The access levels a principal is allowed to see via GET /api/documents."""
    if principal == "anonymous":
        return {AccessLevel.PUBLIC}
    if principal in ("visitor", "member"):
        return {AccessLevel.PUBLIC, AccessLevel.MEMBERS}
    # administrator
    return {AccessLevel.PUBLIC, AccessLevel.MEMBERS, AccessLevel.ADMINISTRATORS}


@pytest.mark.property
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    specs=st.lists(_doc_spec, min_size=0, max_size=9),
    principal=st.sampled_from(["anonymous", "visitor", "member", "administrator"]),
)
def test_property6_role_based_listing_filter(
    client, admin_user, member_user, visitor_user, specs, principal
):
    """Feature: admin-document-upload-categories, Property 6: Role-based listing
    filter.

    For an arbitrary collection of stored documents and any requesting
    principal, GET /api/documents returns exactly the documents whose
    access_level is permitted for that principal.

    Validates: Requirements 5.3
    """
    from tests.conftest import TestingSessionLocal

    _reset_documents()

    # Seed the generated collection.
    db = TestingSessionLocal()
    try:
        expected_permitted = _permitted_levels(principal)
        expected_count = 0
        for i, (al_idx, cat_idx) in enumerate(specs):
            access_level = _ACCESS_LEVELS[al_idx]
            category = _CATEGORIES[cat_idx]
            if access_level in expected_permitted:
                expected_count += 1
            db.add(
                Document(
                    filename=f"gen_{i}_{uuid.uuid4().hex}.pdf",
                    original_name=f"Generated {i}.pdf",
                    mime_type="application/pdf",
                    size=1024,
                    category=category,
                    access_level=access_level,
                    uploaded_by=admin_user.id,
                    download_count=0,
                )
            )
        db.commit()
    finally:
        db.close()

    # Pick headers for the principal.
    if principal == "anonymous":
        headers = None
    elif principal == "visitor":
        headers = _headers(visitor_user)
    elif principal == "member":
        headers = _headers(member_user)
    else:
        headers = _headers(admin_user)

    response = client.get("/api/documents", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Exactly the permitted count is returned...
    assert data["total"] == expected_count
    assert len(data["documents"]) == expected_count
    # ...and every returned document's access level is within the permitted set.
    returned_levels = {doc["access_level"] for doc in data["documents"]}
    permitted_values = {lvl.value for lvl in expected_permitted}
    assert returned_levels <= permitted_values

    _reset_documents()

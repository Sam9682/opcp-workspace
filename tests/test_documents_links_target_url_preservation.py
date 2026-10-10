"""Preservation tests for the "documents-links-html-link" bugfix.

Property 2 (Preservation): Non-links documents render exactly as before, and
the shared list behaviour (role-based access control, ordering) is unchanged.

    isBugCondition(doc) === (doc.category == 'links')

The backend half of preservation is that ``GET /api/documents`` returns the SAME
visible set of documents per role as before, and that adding an optional
``target_url`` field is additive: it is populated only for the ``links``
documents the caller may already see, and left ``None`` for every other
category.

Observation-first methodology: these tests are written and run against the
UNFIXED code. On unfixed code ``DocumentResponse`` has no ``target_url`` field,
so the baseline observation is "no visible document exposes a non-null
``target_url``". They are written so that assertion ALSO holds after the fix:
non-``links`` documents keep ``target_url is None`` and the visible set per role
is identical. They are re-run after the fix (task 3.4) to confirm no
regressions.

Access control rule (preserved):
    - anonymous          -> public only
    - member / visitor   -> public + members
    - administrator      -> all

Validates: Requirements 3.5 (and the access-control half of 3.1-3.4)
"""
import pytest
from fastapi import status
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.models import User, Document
from app.models.document import DocumentCategory, AccessLevel
from app.models.user import UserRole
from app.auth.token import create_access_token


# ---------------------------------------------------------------------------
# Users / auth headers.
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


def _seed_mixed_documents(db_session, uploader) -> list[Document]:
    """Seed documents across categories (incl. links) and access levels."""
    rows = [
        # (filename, original_name, category, access_level)
        ("public_statute.pdf", "Public Statute.pdf", DocumentCategory.DOCUMENTS, AccessLevel.PUBLIC),
        ("public_link.links", "Public Link", DocumentCategory.LINKS, AccessLevel.PUBLIC),
        ("members_report.pdf", "Members Report.pdf", DocumentCategory.SCRIPTS, AccessLevel.MEMBERS),
        ("members_link.links", "Members Link", DocumentCategory.LINKS, AccessLevel.MEMBERS),
        ("admin_link.links", "Admin Link", DocumentCategory.LINKS, AccessLevel.ADMINISTRATORS),
        ("admin_guide.pdf", "Admin Guide.pdf", DocumentCategory.DOCS, AccessLevel.ADMINISTRATORS),
    ]
    documents = []
    for filename, original_name, category, access_level in rows:
        doc = Document(
            filename=filename,
            original_name=original_name,
            mime_type="application/octet-stream",
            size=10,
            category=category,
            access_level=access_level,
            uploaded_by=uploader.id,
            download_count=0,
        )
        db_session.add(doc)
        documents.append(doc)
    db_session.commit()
    for doc in documents:
        db_session.refresh(doc)
    return documents


# The visible original_name set per role over the seeded fixture above.
_EXPECTED_VISIBLE = {
    None: {"Public Statute.pdf", "Public Link"},
    UserRole.VISITOR: {"Public Statute.pdf", "Public Link", "Members Report.pdf", "Members Link"},
    UserRole.MEMBER: {"Public Statute.pdf", "Public Link", "Members Report.pdf", "Members Link"},
    UserRole.ADMINISTRATOR: {
        "Public Statute.pdf",
        "Public Link",
        "Members Report.pdf",
        "Members Link",
        "Admin Link",
        "Admin Guide.pdf",
    },
}


@pytest.mark.parametrize(
    "role",
    [None, UserRole.VISITOR, UserRole.MEMBER, UserRole.ADMINISTRATOR],
)
def test_list_visible_set_preserved_per_role(client, db_session, admin_user, role):
    """The list endpoint returns the same visible set per role as before.

    Preserves Requirement 3.5: role-based access control on the list endpoint is
    unchanged (anonymous -> public; member/visitor -> public + members;
    administrator -> all).
    """
    _seed_mixed_documents(db_session, admin_user)

    headers = {}
    if role is not None:
        viewer = User(
            email=f"viewer_{role.value}@test.com",
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

    assert names == _EXPECTED_VISIBLE[role], (
        f"role={role} expected={_EXPECTED_VISIBLE[role]} got={names}"
    )


@pytest.mark.parametrize(
    "role",
    [None, UserRole.VISITOR, UserRole.MEMBER, UserRole.ADMINISTRATOR],
)
def test_non_links_documents_never_expose_a_target_url(client, db_session, admin_user, role):
    """Non-``links`` documents carry no usable target_url.

    Baseline observation (unfixed): ``DocumentResponse`` has no ``target_url``
    field, so ``dict.get('target_url')`` is ``None`` for every returned document.
    This assertion is written to ALSO hold after the fix, which populates
    ``target_url`` only for ``links`` documents and leaves it ``None`` for every
    other category. Thus it is a genuine preservation guard: whatever the code
    does, a non-``links`` document must never surface a target URL.

    Preserves the "additive, links-only" contract of Requirement 3.5.
    """
    _seed_mixed_documents(db_session, admin_user)

    headers = {}
    if role is not None:
        viewer = User(
            email=f"viewer2_{role.value}@test.com",
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

    for doc in response.json()["documents"]:
        if doc["category"] != DocumentCategory.LINKS.value:
            assert doc.get("target_url") is None, (
                f"non-links document {doc['original_name']} exposed a target_url: "
                f"{doc.get('target_url')!r}"
            )


def test_existing_documentresponse_fields_unchanged(client, db_session, admin_user):
    """Every existing DocumentResponse metadata field is still returned.

    Preserves Requirement 3.5: the response shape (id, filename, original_name,
    mime_type, size, category, access_level, uploaded_by, download_count,
    created_at, updated_at) is unchanged. The new target_url field is additive
    and is NOT asserted here (it does not exist on unfixed code).
    """
    _seed_mixed_documents(db_session, admin_user)

    response = client.get("/api/documents", headers=_headers(admin_user))
    assert response.status_code == status.HTTP_200_OK

    required_fields = [
        "id", "filename", "original_name", "mime_type", "size",
        "category", "access_level", "uploaded_by", "download_count",
        "created_at", "updated_at",
    ]
    for doc in response.json()["documents"]:
        for field in required_fields:
            assert field in doc, f"Missing preserved field: {field}"


# ---------------------------------------------------------------------------
# RBAC preservation (property-based) — for any (viewer role, document
# access_level), a links document is visible in the list iff the current RBAC
# rule permits it. This locks in that target_url is only ever populated for
# links documents the caller may ALREADY see.
# ---------------------------------------------------------------------------
_ROLES = st.sampled_from([None, UserRole.VISITOR, UserRole.MEMBER, UserRole.ADMINISTRATOR])
_ACCESS = st.sampled_from(
    [AccessLevel.PUBLIC, AccessLevel.MEMBERS, AccessLevel.ADMINISTRATORS]
)


def _visible_expected(role, access_level) -> bool:
    if role is None:
        return access_level == AccessLevel.PUBLIC
    if role == UserRole.ADMINISTRATOR:
        return True
    return access_level in (AccessLevel.PUBLIC, AccessLevel.MEMBERS)


@pytest.mark.property
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(role=_ROLES, access_level=_ACCESS)
def test_links_document_visibility_matches_rbac(client, db_session, role, access_level):
    """A links document is listed iff the current RBAC rule permits the viewer.

    Preserves Requirement 3.5: target_url may only be populated for links the
    caller can already see, so visibility must follow the unchanged access rule.
    """
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
        filename="rbac_probe.links",
        original_name="RBAC Probe Link",
        mime_type="text/plain",
        size=10,
        category=DocumentCategory.LINKS,
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
    assert ("RBAC Probe Link" in names) == expected_visible, (
        f"role={role} access_level={access_level} "
        f"expected_visible={expected_visible} got_names={names}"
    )

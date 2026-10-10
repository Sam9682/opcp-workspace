"""Tests for document listing endpoint

Tests the document listing functionality:
- GET /api/documents (list documents with access control)

Validates Requirements 5.1, 5.4
Feature: OPCP-website
"""

import pytest
from fastapi import status
from app.models import User, Document
from app.models.document import DocumentCategory, AccessLevel
from app.auth.token import create_access_token


@pytest.fixture
def admin_user(db_session):
    """Create an administrator user for testing"""
    user = User(
        email="admin@test.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role="administrator",
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def member_user(db_session):
    """Create a regular member user for testing"""
    user = User(
        email="member@test.com",
        password_hash="hashed_password",
        first_name="Member",
        last_name="User",
        role="member",
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def visitor_user(db_session):
    """Create a visitor user for testing"""
    user = User(
        email="visitor@test.com",
        password_hash="hashed_password",
        first_name="Visitor",
        last_name="User",
        role="visitor",
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(admin_user):
    """Create authentication headers for admin user"""
    token = create_access_token({"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def member_headers(member_user):
    """Create authentication headers for member user"""
    token = create_access_token({"sub": str(member_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def visitor_headers(visitor_user):
    """Create authentication headers for visitor user"""
    token = create_access_token({"sub": str(visitor_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_documents(db_session, admin_user):
    """Create sample documents with different access levels and categories"""
    documents = [
        # Public documents
        Document(
            filename="public_statute_123.pdf",
            original_name="Public Statute.pdf",
            mime_type="application/pdf",
            size=1024000,
            category=DocumentCategory.DOCUMENTS,
            access_level=AccessLevel.PUBLIC,
            uploaded_by=admin_user.id,
            download_count=0
        ),
        Document(
            filename="public_minutes_456.pdf",
            original_name="Public Minutes.pdf",
            mime_type="application/pdf",
            size=2048000,
            category=DocumentCategory.SCRIPTS,
            access_level=AccessLevel.PUBLIC,
            uploaded_by=admin_user.id,
            download_count=5
        ),
        # Members documents
        Document(
            filename="members_report_789.pdf",
            original_name="Members Financial Report.pdf",
            mime_type="application/pdf",
            size=3072000,
            category=DocumentCategory.LINKS,
            access_level=AccessLevel.MEMBERS,
            uploaded_by=admin_user.id,
            download_count=10
        ),
        Document(
            filename="members_other_012.pdf",
            original_name="Members Document.pdf",
            mime_type="application/pdf",
            size=1536000,
            category=DocumentCategory.DOCUMENTS,
            access_level=AccessLevel.MEMBERS,
            uploaded_by=admin_user.id,
            download_count=3
        ),
        # Administrators documents
        Document(
            filename="admin_confidential_345.pdf",
            original_name="Admin Confidential.pdf",
            mime_type="application/pdf",
            size=4096000,
            category=DocumentCategory.LINKS,
            access_level=AccessLevel.ADMINISTRATORS,
            uploaded_by=admin_user.id,
            download_count=1
        ),
        Document(
            filename="admin_minutes_678.pdf",
            original_name="Admin Board Minutes.pdf",
            mime_type="application/pdf",
            size=2560000,
            category=DocumentCategory.SCRIPTS,
            access_level=AccessLevel.ADMINISTRATORS,
            uploaded_by=admin_user.id,
            download_count=2
        ),
    ]
    
    for doc in documents:
        db_session.add(doc)
    db_session.commit()
    
    return documents


def test_list_documents_unauthenticated_only_public(client, sample_documents):
    """Test unauthenticated users can only see public documents
    
    Validates Requirement 5.1: Access control based on user role
    """
    response = client.get("/api/documents")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert "documents" in data
    assert "total" in data
    assert data["total"] == 2  # Only 2 public documents
    
    # Verify all returned documents are public
    for doc in data["documents"]:
        assert doc["access_level"] == AccessLevel.PUBLIC.value
    
    # Verify document IDs match public documents
    returned_names = {doc["original_name"] for doc in data["documents"]}
    assert "Public Statute.pdf" in returned_names
    assert "Public Minutes.pdf" in returned_names


def test_list_documents_member_sees_public_and_members(client, member_headers, sample_documents):
    """Test members can see public and members documents
    
    Validates Requirement 5.1: Access control based on user role
    """
    response = client.get("/api/documents", headers=member_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["total"] == 4  # 2 public + 2 members documents
    
    # Verify returned documents are public or members only
    access_levels = {doc["access_level"] for doc in data["documents"]}
    assert access_levels == {AccessLevel.PUBLIC.value, AccessLevel.MEMBERS.value}
    
    # Verify no admin documents are returned
    for doc in data["documents"]:
        assert doc["access_level"] != AccessLevel.ADMINISTRATORS.value


def test_list_documents_visitor_sees_public_and_members(client, visitor_headers, sample_documents):
    """Test visitors can see public and members documents
    
    Validates Requirement 5.1: Access control based on user role
    """
    response = client.get("/api/documents", headers=visitor_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["total"] == 4  # 2 public + 2 members documents
    
    # Verify returned documents are public or members only
    access_levels = {doc["access_level"] for doc in data["documents"]}
    assert access_levels == {AccessLevel.PUBLIC.value, AccessLevel.MEMBERS.value}


def test_list_documents_admin_sees_all(client, admin_headers, sample_documents):
    """Test administrators can see all documents
    
    Validates Requirement 5.1: Access control based on user role
    """
    response = client.get("/api/documents", headers=admin_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["total"] == 6  # All documents
    
    # Verify all access levels are present
    access_levels = {doc["access_level"] for doc in data["documents"]}
    assert access_levels == {
        AccessLevel.PUBLIC.value,
        AccessLevel.MEMBERS.value,
        AccessLevel.ADMINISTRATORS.value
    }


def test_list_documents_filter_by_category_documents(client, admin_headers, sample_documents):
    """Test filtering documents by category (documents)

    Validates Requirement 5.4: Documents organized by categories
    """
    response = client.get(
        "/api/documents",
        params={"category": DocumentCategory.DOCUMENTS.value},
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["total"] == 2  # Public Statute + Members Document
    for doc in data["documents"]:
        assert doc["category"] == DocumentCategory.DOCUMENTS.value


def test_list_documents_filter_by_category_scripts(client, admin_headers, sample_documents):
    """Test filtering documents by category (scripts)

    Validates Requirement 5.4: Documents organized by categories
    """
    response = client.get(
        "/api/documents",
        params={"category": DocumentCategory.SCRIPTS.value},
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["total"] == 2  # Public Minutes + Admin Board Minutes
    for doc in data["documents"]:
        assert doc["category"] == DocumentCategory.SCRIPTS.value


def test_list_documents_filter_by_category_links(client, admin_headers, sample_documents):
    """Test filtering documents by category (links)

    Validates Requirement 5.4: Documents organized by categories
    """
    response = client.get(
        "/api/documents",
        params={"category": DocumentCategory.LINKS.value},
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["total"] == 2  # Members Financial Report + Admin Confidential
    for doc in data["documents"]:
        assert doc["category"] == DocumentCategory.LINKS.value


def test_list_documents_filter_category_with_access_control(client, member_headers, sample_documents):
    """Test category filter combined with access control
    
    Validates Requirements 5.1, 5.4: Category filtering respects access control
    """
    # Member requests links - should only see the members document, not the admin one
    response = client.get(
        "/api/documents",
        params={"category": DocumentCategory.LINKS.value},
        headers=member_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["total"] == 1  # Only Members Financial Report (LINKS, members)
    assert data["documents"][0]["original_name"] == "Members Financial Report.pdf"
    assert data["documents"][0]["access_level"] == AccessLevel.MEMBERS.value


def test_list_documents_empty_result(client, admin_headers, db_session, admin_user):
    """Test listing documents when no documents match criteria
    
    Validates Requirement 5.1: Handle empty results gracefully
    """
    # Create a document with a specific category
    doc = Document(
        filename="test_123.pdf",
        original_name="Test.pdf",
        mime_type="application/pdf",
        size=1024,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.PUBLIC,
        uploaded_by=admin_user.id,
        download_count=0
    )
    db_session.add(doc)
    db_session.commit()
    
    # Request a different category
    response = client.get(
        "/api/documents",
        params={"category": DocumentCategory.SCRIPTS.value},
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["total"] == 0
    assert data["documents"] == []


def test_list_documents_no_documents_in_database(client, admin_headers):
    """Test listing documents when database is empty
    
    Validates Requirement 5.1: Handle empty database gracefully
    """
    response = client.get("/api/documents", headers=admin_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["total"] == 0
    assert data["documents"] == []


def test_list_documents_response_structure(client, admin_headers, sample_documents):
    """Test document response includes all required metadata
    
    Validates Requirement 5.1: Return document metadata
    """
    response = client.get("/api/documents", headers=admin_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["total"] > 0
    
    # Verify first document has all required fields
    doc = data["documents"][0]
    required_fields = [
        "id", "filename", "original_name", "mime_type", "size",
        "category", "access_level", "uploaded_by", "download_count",
        "created_at", "updated_at"
    ]
    
    for field in required_fields:
        assert field in doc, f"Missing required field: {field}"
    
    # Verify field types
    assert isinstance(doc["id"], str)
    assert isinstance(doc["filename"], str)
    assert isinstance(doc["original_name"], str)
    assert isinstance(doc["mime_type"], str)
    assert isinstance(doc["size"], int)
    assert isinstance(doc["category"], str)
    assert isinstance(doc["access_level"], str)
    assert isinstance(doc["uploaded_by"], str)
    assert isinstance(doc["download_count"], int)
    assert isinstance(doc["created_at"], str)
    assert isinstance(doc["updated_at"], str)


def test_list_documents_ordered_by_created_at_desc(client, admin_headers, db_session, admin_user):
    """Test documents are ordered by created_at descending (newest first)
    
    Validates Requirement 5.1: Documents ordered by creation date
    """
    import time
    
    # Create documents with slight time delays to ensure different timestamps
    doc1 = Document(
        filename="old_doc.pdf",
        original_name="Old Document.pdf",
        mime_type="application/pdf",
        size=1024,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.PUBLIC,
        uploaded_by=admin_user.id,
        download_count=0
    )
    db_session.add(doc1)
    db_session.commit()
    
    time.sleep(0.01)  # Small delay
    
    doc2 = Document(
        filename="new_doc.pdf",
        original_name="New Document.pdf",
        mime_type="application/pdf",
        size=1024,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.PUBLIC,
        uploaded_by=admin_user.id,
        download_count=0
    )
    db_session.add(doc2)
    db_session.commit()
    
    response = client.get("/api/documents", headers=admin_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Newest document should be first
    assert data["documents"][0]["original_name"] == "New Document.pdf"
    assert data["documents"][1]["original_name"] == "Old Document.pdf"


def test_list_documents_invalid_category(client, admin_headers):
    """Test listing documents with invalid category parameter
    
    Validates Requirement 5.4: Handle invalid category gracefully
    """
    response = client.get(
        "/api/documents",
        params={"category": "invalid_category"},
        headers=admin_headers
    )
    
    # The app's validation handler maps request validation errors to a
    # structured 400 response.
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_documents_unauthenticated_with_category_filter(client, sample_documents):
    """Test unauthenticated users can filter by category
    
    Validates Requirements 5.1, 5.4: Category filtering works for unauthenticated users
    """
    response = client.get(
        "/api/documents",
        params={"category": DocumentCategory.DOCUMENTS.value}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Anonymous sees only the single public DOCUMENTS item (Public Statute);
    # the members-only DOCUMENTS item is filtered out.
    assert data["total"] == 1
    assert data["documents"][0]["category"] == DocumentCategory.DOCUMENTS.value
    assert data["documents"][0]["access_level"] == AccessLevel.PUBLIC.value

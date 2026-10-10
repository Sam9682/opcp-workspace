"""Tests for document download endpoint

Tests the document download functionality:
- GET /api/documents/{document_id}/download

Validates Requirements 5.3
Feature: OPCP-website
"""

import pytest
from fastapi import status
from app.models import User, Document
from app.models.document import DocumentCategory, AccessLevel
from app.auth.token import create_access_token
from app.services.storage_service import storage_service
from pathlib import Path


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
def sample_file_content():
    """Create sample file content for testing"""
    return b"This is a test PDF document content"


@pytest.fixture
def public_document(db_session, admin_user, sample_file_content):
    """Create a public document with actual file"""
    # Save file to storage
    unique_filename, file_path = storage_service.save_file(
        file_content=sample_file_content,
        original_filename="public_test.pdf"
    )
    
    # Create document record
    document = Document(
        filename=unique_filename,
        original_name="Public Test Document.pdf",
        mime_type="application/pdf",
        size=len(sample_file_content),
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.PUBLIC,
        uploaded_by=admin_user.id,
        download_count=0
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    yield document
    
    # Cleanup: delete file after test
    storage_service.delete_file(unique_filename)


@pytest.fixture
def members_document(db_session, admin_user, sample_file_content):
    """Create a members-only document with actual file"""
    # Save file to storage
    unique_filename, file_path = storage_service.save_file(
        file_content=sample_file_content,
        original_filename="members_test.pdf"
    )
    
    # Create document record
    document = Document(
        filename=unique_filename,
        original_name="Members Test Document.pdf",
        mime_type="application/pdf",
        size=len(sample_file_content),
        category=DocumentCategory.LINKS,
        access_level=AccessLevel.MEMBERS,
        uploaded_by=admin_user.id,
        download_count=0
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    yield document
    
    # Cleanup: delete file after test
    storage_service.delete_file(unique_filename)


@pytest.fixture
def admin_document(db_session, admin_user, sample_file_content):
    """Create an admin-only document with actual file"""
    # Save file to storage
    unique_filename, file_path = storage_service.save_file(
        file_content=sample_file_content,
        original_filename="admin_test.pdf"
    )
    
    # Create document record
    document = Document(
        filename=unique_filename,
        original_name="Admin Test Document.pdf",
        mime_type="application/pdf",
        size=len(sample_file_content),
        category=DocumentCategory.SCRIPTS,
        access_level=AccessLevel.ADMINISTRATORS,
        uploaded_by=admin_user.id,
        download_count=0
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    yield document
    
    # Cleanup: delete file after test
    storage_service.delete_file(unique_filename)


def test_download_public_document_unauthenticated(client, public_document, sample_file_content):
    """Test unauthenticated users can download public documents
    
    Validates Requirement 5.3: Public documents accessible to everyone
    """
    response = client.get(f"/api/documents/{public_document.id}/download")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == sample_file_content
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert "Public Test Document.pdf" in response.headers["content-disposition"]


def test_download_public_document_member(client, member_headers, public_document, sample_file_content):
    """Test members can download public documents
    
    Validates Requirement 5.3: Public documents accessible to members
    """
    response = client.get(
        f"/api/documents/{public_document.id}/download",
        headers=member_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == sample_file_content


def test_download_public_document_admin(client, admin_headers, public_document, sample_file_content):
    """Test administrators can download public documents
    
    Validates Requirement 5.3: Public documents accessible to admins
    """
    response = client.get(
        f"/api/documents/{public_document.id}/download",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == sample_file_content


def test_download_members_document_unauthenticated_denied(client, members_document):
    """Test unauthenticated users cannot download members documents
    
    Validates Requirement 5.3: Access control enforcement
    """
    response = client.get(f"/api/documents/{members_document.id}/download")
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert data["detail"]["error"]["code"] == "ACCESS_DENIED"
    assert "logged in" in data["detail"]["error"]["message"].lower()


def test_download_members_document_member(client, member_headers, members_document, sample_file_content):
    """Test members can download members documents
    
    Validates Requirement 5.3: Members can access member documents
    """
    response = client.get(
        f"/api/documents/{members_document.id}/download",
        headers=member_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == sample_file_content


def test_download_members_document_visitor(client, visitor_headers, members_document, sample_file_content):
    """Test visitors can download members documents
    
    Validates Requirement 5.3: Visitors can access member documents
    """
    response = client.get(
        f"/api/documents/{members_document.id}/download",
        headers=visitor_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == sample_file_content


def test_download_members_document_admin(client, admin_headers, members_document, sample_file_content):
    """Test administrators can download members documents
    
    Validates Requirement 5.3: Admins can access member documents
    """
    response = client.get(
        f"/api/documents/{members_document.id}/download",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == sample_file_content


def test_download_admin_document_unauthenticated_denied(client, admin_document):
    """Test unauthenticated users cannot download admin documents
    
    Validates Requirement 5.3: Access control enforcement for admin documents
    """
    response = client.get(f"/api/documents/{admin_document.id}/download")
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert data["detail"]["error"]["code"] == "ACCESS_DENIED"


def test_download_admin_document_member_denied(client, member_headers, admin_document):
    """Test members cannot download admin documents
    
    Validates Requirement 5.3: Members cannot access admin documents
    """
    response = client.get(
        f"/api/documents/{admin_document.id}/download",
        headers=member_headers
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert data["detail"]["error"]["code"] == "ACCESS_DENIED"


def test_download_admin_document_visitor_denied(client, visitor_headers, admin_document):
    """Test visitors cannot download admin documents
    
    Validates Requirement 5.3: Visitors cannot access admin documents
    """
    response = client.get(
        f"/api/documents/{admin_document.id}/download",
        headers=visitor_headers
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert data["detail"]["error"]["code"] == "ACCESS_DENIED"


def test_download_admin_document_admin(client, admin_headers, admin_document, sample_file_content):
    """Test administrators can download admin documents
    
    Validates Requirement 5.3: Admins can access admin documents
    """
    response = client.get(
        f"/api/documents/{admin_document.id}/download",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == sample_file_content


def test_download_increments_count(client, admin_headers, public_document, db_session):
    """Test download increments download_count
    
    Validates Requirement 5.3: Track download statistics
    """
    initial_count = public_document.download_count
    
    # Download document
    response = client.get(
        f"/api/documents/{public_document.id}/download",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Refresh document from database
    db_session.refresh(public_document)
    
    # Verify count incremented
    assert public_document.download_count == initial_count + 1


def test_download_multiple_times_increments_count(client, member_headers, public_document, db_session):
    """Test multiple downloads increment count correctly
    
    Validates Requirement 5.3: Track multiple downloads
    """
    initial_count = public_document.download_count
    
    # Download document 3 times
    for i in range(3):
        response = client.get(
            f"/api/documents/{public_document.id}/download",
            headers=member_headers
        )
        assert response.status_code == status.HTTP_200_OK
    
    # Refresh document from database
    db_session.refresh(public_document)
    
    # Verify count incremented by 3
    assert public_document.download_count == initial_count + 3


def test_download_nonexistent_document(client, admin_headers):
    """Test downloading non-existent document returns 404
    
    Validates Requirement 5.3: Handle missing documents
    """
    import uuid
    fake_id = uuid.uuid4()
    
    response = client.get(
        f"/api/documents/{fake_id}/download",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert data["detail"]["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_download_invalid_document_id(client, admin_headers):
    """Test downloading with invalid UUID returns 422
    
    Validates Requirement 5.3: Handle invalid input
    """
    response = client.get(
        "/api/documents/invalid-uuid/download",
        headers=admin_headers
    )
    
    # FastAPI returns 422 for invalid UUID format
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_download_document_file_not_found(client, admin_headers, db_session, admin_user):
    """Test downloading document when file is missing from storage
    
    Validates Requirement 5.3: Handle file system errors
    """
    # Create document record without actual file
    document = Document(
        filename="nonexistent_file.pdf",
        original_name="Missing File.pdf",
        mime_type="application/pdf",
        size=1024,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.PUBLIC,
        uploaded_by=admin_user.id,
        download_count=0
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    response = client.get(
        f"/api/documents/{document.id}/download",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert data["detail"]["error"]["code"] == "FILE_NOT_FOUND"


def test_download_response_headers(client, admin_headers, public_document):
    """Test download response includes correct headers
    
    Validates Requirement 5.3: Return file with correct content-type
    """
    response = client.get(
        f"/api/documents/{public_document.id}/download",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Verify content-type header
    assert response.headers["content-type"] == public_document.mime_type
    
    # Verify content-disposition header
    assert "content-disposition" in response.headers
    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    assert public_document.original_name in disposition


def test_download_different_mime_types(client, admin_headers, db_session, admin_user):
    """Test downloading documents with different MIME types
    
    Validates Requirement 5.3: Support various file formats
    """
    test_cases = [
        ("test.pdf", "application/pdf", b"PDF content"),
        ("test.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"DOCX content"),
        ("test.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"XLSX content"),
        ("test.jpg", "image/jpeg", b"JPEG content"),
    ]
    
    for original_name, mime_type, content in test_cases:
        # Save file to storage
        unique_filename, file_path = storage_service.save_file(
            file_content=content,
            original_filename=original_name
        )
        
        # Create document record
        document = Document(
            filename=unique_filename,
            original_name=original_name,
            mime_type=mime_type,
            size=len(content),
            category=DocumentCategory.OTHER,
            access_level=AccessLevel.PUBLIC,
            uploaded_by=admin_user.id,
            download_count=0
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        
        # Download document
        response = client.get(
            f"/api/documents/{document.id}/download",
            headers=admin_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.content == content
        assert response.headers["content-type"] == mime_type
        
        # Cleanup
        storage_service.delete_file(unique_filename)


def test_download_preserves_original_filename(client, admin_headers, public_document):
    """Test download uses original filename in response
    
    Validates Requirement 5.3: Preserve original filename for user
    """
    response = client.get(
        f"/api/documents/{public_document.id}/download",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Verify original filename is in content-disposition header
    disposition = response.headers["content-disposition"]
    assert public_document.original_name in disposition
    assert public_document.filename not in disposition  # Unique filename should not be exposed


def test_download_count_starts_at_zero(client, admin_headers, public_document, db_session):
    """Test new documents have download_count of 0
    
    Validates Requirement 5.3: Initialize download count correctly
    """
    # Verify initial count is 0
    assert public_document.download_count == 0
    
    # Download once
    response = client.get(
        f"/api/documents/{public_document.id}/download",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Refresh and verify count is now 1
    db_session.refresh(public_document)
    assert public_document.download_count == 1

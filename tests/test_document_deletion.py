"""Tests for document deletion endpoint

Tests the document deletion functionality:
- DELETE /api/documents/:id (delete document - admin only)

Validates Requirements 5.7
Feature: OPCP-website
"""

import pytest
import io
from fastapi import status
from app.models import User, Document, AuditLog
from app.models.document import DocumentCategory, AccessLevel
from app.auth.token import create_access_token
from app.services.storage_service import storage_service


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
def sample_document(db_session, admin_user):
    """Create a sample document with file in storage"""
    # Create a fake PDF file in storage
    pdf_content = b"%PDF-1.4\n%Test PDF content"
    unique_filename, file_path = storage_service.save_file(
        file_content=pdf_content,
        original_filename="test_document.pdf"
    )
    
    # Create document record
    document = Document(
        filename=unique_filename,
        original_name="test_document.pdf",
        mime_type="application/pdf",
        size=len(pdf_content),
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.MEMBERS,
        uploaded_by=admin_user.id,
        download_count=0
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_delete_document_success(client, admin_user, admin_headers, db_session, sample_document):
    """Test successful document deletion by administrator
    
    Validates Requirement 5.7: Administrator deletes document, system removes file and metadata
    """
    document_id = sample_document.id
    filename = sample_document.filename
    
    # Verify file exists in storage before deletion
    file_path = storage_service.get_file_path(filename)
    assert file_path is not None
    assert file_path.exists()
    
    # Delete document
    response = client.delete(
        f"/api/documents/{document_id}",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Verify response structure
    assert data["success"] is True
    assert data["message"] == "Document deleted successfully"
    assert data["document_id"] == str(document_id)
    
    # Verify document was deleted from database
    document = db_session.query(Document).filter(Document.id == document_id).first()
    assert document is None
    
    # Verify file was deleted from storage
    file_path = storage_service.get_file_path(filename)
    assert file_path is None
    
    # Verify audit log entry was created
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DELETE",
        AuditLog.target_id == document_id
    ).first()
    assert audit_entry is not None
    assert audit_entry.admin_id == admin_user.id
    assert audit_entry.target_type == "document"
    assert "document_id" in audit_entry.details
    assert "original_name" in audit_entry.details


def test_delete_document_not_found(client, admin_user, admin_headers, db_session):
    """Test document deletion fails when document doesn't exist
    
    Validates Requirement 5.7: System handles non-existent documents
    """
    # Use a random UUID that doesn't exist
    fake_id = "00000000-0000-0000-0000-000000000000"
    
    response = client.delete(
        f"/api/documents/{fake_id}",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert data["detail"]["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_delete_document_non_admin_forbidden(client, member_user, member_headers, sample_document):
    """Test document deletion fails for non-admin users
    
    Validates Requirement 7.2: Administrative functions restricted to administrators
    """
    document_id = sample_document.id
    
    response = client.delete(
        f"/api/documents/{document_id}",
        headers=member_headers
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert "detail" in data
    assert "error" in data["detail"]
    assert data["detail"]["error"]["code"] == "ADMIN_ACCESS_REQUIRED"


def test_delete_document_unauthenticated(client, sample_document):
    """Test document deletion fails without authentication"""
    document_id = sample_document.id
    
    response = client.delete(f"/api/documents/{document_id}")
    
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_delete_document_file_missing_from_storage(client, admin_user, admin_headers, db_session):
    """Test document deletion succeeds even if file is missing from storage
    
    Validates Requirement 5.7: System handles missing files gracefully
    """
    # Create document record without actual file in storage
    document = Document(
        filename="nonexistent_file.pdf",
        original_name="missing.pdf",
        mime_type="application/pdf",
        size=1000,
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.MEMBERS,
        uploaded_by=admin_user.id,
        download_count=0
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    
    document_id = document.id
    
    # Delete document
    response = client.delete(
        f"/api/documents/{document_id}",
        headers=admin_headers
    )
    
    # Should succeed even though file doesn't exist
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    
    # Verify document was deleted from database
    document = db_session.query(Document).filter(Document.id == document_id).first()
    assert document is None


def test_delete_document_multiple_documents(client, admin_user, admin_headers, db_session):
    """Test deleting multiple documents sequentially
    
    Validates Requirement 5.7: System can delete multiple documents
    """
    # Create multiple documents
    documents = []
    for i in range(3):
        pdf_content = b"%PDF-1.4\n%Test PDF content"
        unique_filename, file_path = storage_service.save_file(
            file_content=pdf_content,
            original_filename=f"test_document_{i}.pdf"
        )
        
        document = Document(
            filename=unique_filename,
            original_name=f"test_document_{i}.pdf",
            mime_type="application/pdf",
            size=len(pdf_content),
            category=DocumentCategory.OTHER,
            access_level=AccessLevel.MEMBERS,
            uploaded_by=admin_user.id,
            download_count=0
        )
        db_session.add(document)
        documents.append(document)
    
    db_session.commit()
    
    # Delete all documents
    for document in documents:
        response = client.delete(
            f"/api/documents/{document.id}",
            headers=admin_headers
        )
        assert response.status_code == status.HTTP_200_OK
    
    # Verify all documents were deleted
    for document in documents:
        db_doc = db_session.query(Document).filter(Document.id == document.id).first()
        assert db_doc is None


def test_delete_document_invalid_uuid(client, admin_headers):
    """Test document deletion with invalid UUID format"""
    response = client.delete(
        "/api/documents/not-a-valid-uuid",
        headers=admin_headers
    )
    
    # FastAPI should return 422 for invalid UUID format
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_delete_document_audit_log_details(client, admin_user, admin_headers, db_session, sample_document):
    """Test that audit log contains all required details
    
    Validates Requirement 7.5: Administrative actions are logged with details
    """
    document_id = sample_document.id
    original_name = sample_document.original_name
    category = sample_document.category
    access_level = sample_document.access_level
    
    # Delete document
    response = client.delete(
        f"/api/documents/{document_id}",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Verify audit log details
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DELETE",
        AuditLog.target_id == document_id
    ).first()
    
    assert audit_entry is not None
    assert audit_entry.details["document_id"] == str(document_id)
    assert audit_entry.details["original_name"] == original_name
    assert audit_entry.details["category"] == category.value
    assert audit_entry.details["access_level"] == access_level.value
    assert "filename" in audit_entry.details

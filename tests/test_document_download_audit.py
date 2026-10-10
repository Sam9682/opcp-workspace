"""Tests for document download audit logging

Tests that document downloads are properly logged in the audit log.

Validates Requirements 5.3
Feature: OPCP-website
"""

import pytest
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


def test_download_creates_audit_log_authenticated(client, admin_headers, public_document, db_session, admin_user):
    """Test that downloading a document creates an audit log entry for authenticated users
    
    Validates Requirement 5.3: Log download in audit log
    """
    # Get initial audit log count
    initial_count = db_session.query(AuditLog).count()
    
    # Download document
    response = client.get(
        f"/api/documents/{public_document.id}/download",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Verify audit log entry was created
    audit_logs = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DOWNLOAD",
        AuditLog.target_id == public_document.id
    ).all()
    
    assert len(audit_logs) == 1
    audit_log = audit_logs[0]
    
    # Verify audit log details
    assert audit_log.admin_id == admin_user.id
    assert audit_log.action == "DOCUMENT_DOWNLOAD"
    assert audit_log.target_type == "document"
    assert audit_log.target_id == public_document.id
    assert audit_log.details is not None
    assert audit_log.details["document_id"] == str(public_document.id)
    assert audit_log.details["document_name"] == public_document.original_name
    assert audit_log.details["category"] == public_document.category.value
    assert audit_log.details["access_level"] == public_document.access_level.value
    assert audit_log.details["user_role"] == "administrator"
    
    # Verify total audit log count increased
    final_count = db_session.query(AuditLog).count()
    assert final_count == initial_count + 1


def test_download_creates_audit_log_unauthenticated(client, public_document, db_session):
    """Test that downloading a document creates an audit log entry for unauthenticated users
    
    Validates Requirement 5.3: Log download in audit log for anonymous users
    """
    # Get initial audit log count
    initial_count = db_session.query(AuditLog).count()
    
    # Download document without authentication
    response = client.get(f"/api/documents/{public_document.id}/download")
    
    assert response.status_code == status.HTTP_200_OK
    
    # Verify audit log entry was created
    audit_logs = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DOWNLOAD",
        AuditLog.target_id == public_document.id
    ).all()
    
    assert len(audit_logs) == 1
    audit_log = audit_logs[0]
    
    # Verify audit log details for anonymous user
    assert audit_log.admin_id is None  # No user ID for anonymous
    assert audit_log.action == "DOCUMENT_DOWNLOAD"
    assert audit_log.target_type == "document"
    assert audit_log.target_id == public_document.id
    assert audit_log.details is not None
    assert audit_log.details["document_id"] == str(public_document.id)
    assert audit_log.details["document_name"] == public_document.original_name
    assert audit_log.details["user_role"] == "anonymous"
    
    # Verify total audit log count increased
    final_count = db_session.query(AuditLog).count()
    assert final_count == initial_count + 1


def test_download_multiple_times_creates_multiple_audit_logs(client, member_headers, public_document, db_session, member_user):
    """Test that multiple downloads create multiple audit log entries
    
    Validates Requirement 5.3: Each download is logged separately
    """
    # Get initial audit log count for this document
    initial_count = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DOWNLOAD",
        AuditLog.target_id == public_document.id
    ).count()
    
    # Download document 3 times
    for i in range(3):
        response = client.get(
            f"/api/documents/{public_document.id}/download",
            headers=member_headers
        )
        assert response.status_code == status.HTTP_200_OK
    
    # Verify 3 audit log entries were created
    audit_logs = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DOWNLOAD",
        AuditLog.target_id == public_document.id,
        AuditLog.admin_id == member_user.id
    ).all()
    
    assert len(audit_logs) == initial_count + 3
    
    # Verify all entries have correct details
    for audit_log in audit_logs:
        assert audit_log.admin_id == member_user.id
        assert audit_log.action == "DOCUMENT_DOWNLOAD"
        assert audit_log.target_type == "document"
        assert audit_log.target_id == public_document.id


def test_download_different_documents_creates_separate_audit_logs(
    client, admin_headers, public_document, members_document, db_session, admin_user
):
    """Test that downloading different documents creates separate audit log entries
    
    Validates Requirement 5.3: Audit logs track individual document downloads
    """
    # Download first document
    response1 = client.get(
        f"/api/documents/{public_document.id}/download",
        headers=admin_headers
    )
    assert response1.status_code == status.HTTP_200_OK
    
    # Download second document
    response2 = client.get(
        f"/api/documents/{members_document.id}/download",
        headers=admin_headers
    )
    assert response2.status_code == status.HTTP_200_OK
    
    # Verify separate audit log entries exist
    audit_log_1 = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DOWNLOAD",
        AuditLog.target_id == public_document.id,
        AuditLog.admin_id == admin_user.id
    ).first()
    
    audit_log_2 = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DOWNLOAD",
        AuditLog.target_id == members_document.id,
        AuditLog.admin_id == admin_user.id
    ).first()
    
    assert audit_log_1 is not None
    assert audit_log_2 is not None
    assert audit_log_1.id != audit_log_2.id
    assert audit_log_1.details["document_name"] == public_document.original_name
    assert audit_log_2.details["document_name"] == members_document.original_name


def test_download_audit_log_includes_all_required_fields(client, member_headers, members_document, db_session, member_user):
    """Test that audit log includes all required fields
    
    Validates Requirement 5.3: Audit log contains complete information
    """
    # Download document
    response = client.get(
        f"/api/documents/{members_document.id}/download",
        headers=member_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Retrieve audit log entry
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DOWNLOAD",
        AuditLog.target_id == members_document.id
    ).first()
    
    assert audit_log is not None
    
    # Verify all required fields are present
    assert audit_log.id is not None
    assert audit_log.admin_id == member_user.id
    assert audit_log.action == "DOCUMENT_DOWNLOAD"
    assert audit_log.target_type == "document"
    assert audit_log.target_id == members_document.id
    assert audit_log.timestamp is not None
    
    # Verify details dictionary contains all expected keys
    assert "document_id" in audit_log.details
    assert "document_name" in audit_log.details
    assert "category" in audit_log.details
    assert "access_level" in audit_log.details
    assert "user_role" in audit_log.details
    
    # Verify details values are correct
    assert audit_log.details["document_id"] == str(members_document.id)
    assert audit_log.details["document_name"] == members_document.original_name
    assert audit_log.details["category"] == DocumentCategory.LINKS.value
    assert audit_log.details["access_level"] == AccessLevel.MEMBERS.value
    assert audit_log.details["user_role"] == "member"


def test_failed_download_does_not_create_audit_log(client, member_headers, db_session):
    """Test that failed downloads (e.g., document not found) do not create audit logs
    
    Validates Requirement 5.3: Only successful downloads are logged
    """
    import uuid
    fake_id = uuid.uuid4()
    
    # Get initial audit log count
    initial_count = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DOWNLOAD"
    ).count()
    
    # Attempt to download non-existent document
    response = client.get(
        f"/api/documents/{fake_id}/download",
        headers=member_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    # Verify no audit log entry was created
    final_count = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DOWNLOAD"
    ).count()
    
    assert final_count == initial_count


def test_access_denied_download_does_not_create_audit_log(client, member_headers, db_session, admin_user, sample_file_content):
    """Test that access denied downloads do not create audit logs
    
    Validates Requirement 5.3: Only successful downloads are logged
    """
    # Create an admin-only document
    unique_filename, file_path = storage_service.save_file(
        file_content=sample_file_content,
        original_filename="admin_only.pdf"
    )
    
    admin_document = Document(
        filename=unique_filename,
        original_name="Admin Only Document.pdf",
        mime_type="application/pdf",
        size=len(sample_file_content),
        category=DocumentCategory.SCRIPTS,
        access_level=AccessLevel.ADMINISTRATORS,
        uploaded_by=admin_user.id,
        download_count=0
    )
    db_session.add(admin_document)
    db_session.commit()
    db_session.refresh(admin_document)
    
    # Get initial audit log count
    initial_count = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DOWNLOAD",
        AuditLog.target_id == admin_document.id
    ).count()
    
    # Attempt to download as member (should be denied)
    response = client.get(
        f"/api/documents/{admin_document.id}/download",
        headers=member_headers
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    
    # Verify no audit log entry was created
    final_count = db_session.query(AuditLog).filter(
        AuditLog.action == "DOCUMENT_DOWNLOAD",
        AuditLog.target_id == admin_document.id
    ).count()
    
    assert final_count == initial_count
    
    # Cleanup
    storage_service.delete_file(unique_filename)

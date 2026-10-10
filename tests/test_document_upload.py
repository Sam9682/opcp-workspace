"""Tests for document upload endpoint

Tests the document upload functionality:
- POST /api/documents/upload (upload document - admin only)

The category is now server-assigned from the file extension; the endpoint no
longer accepts a client-supplied ``category`` form field.

Validates Requirements 2.4, 3.4, 3.5, 4.3, 5.2
Feature: admin-document-upload-categories
"""

import pytest
import io
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
def admin_headers(admin_user):
    """Create authentication headers for admin user"""
    token = create_access_token({"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def member_headers(member_user):
    """Create authentication headers for member user"""
    token = create_access_token({"sub": str(member_user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_upload_document_success_pdf(client, admin_user, admin_headers, db_session):
    """Test successful document upload with PDF file

    Validates Requirement 5.2: Administrator uploads document and system stores it
    Validates Requirement 2.1: pdf classified as ``documents``
    """
    pdf_content = b"%PDF-1.4\n%Test PDF content"

    response = client.post(
        "/api/documents/upload",
        files={"file": ("test_document.pdf", io.BytesIO(pdf_content), "application/pdf")},
        data={"access_level": AccessLevel.MEMBERS.value},
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    # Verify response structure
    assert data["success"] is True
    assert data["message"] == "Document uploaded successfully"
    assert "document" in data

    doc = data["document"]
    assert "id" in doc
    assert doc["original_name"] == "test_document.pdf"
    assert doc["mime_type"] == "application/pdf"
    assert doc["size"] == len(pdf_content)
    # Category is server-assigned from the extension.
    assert doc["category"] == DocumentCategory.DOCUMENTS.value
    assert doc["access_level"] == AccessLevel.MEMBERS.value
    assert doc["uploaded_by"] == str(admin_user.id)
    assert doc["download_count"] == 0
    assert "filename" in doc  # Unique filename
    assert doc["filename"] != "test_document.pdf"  # Should be unique

    # Verify document was created in database
    document = db_session.query(Document).filter(
        Document.original_name == "test_document.pdf"
    ).first()
    assert document is not None
    assert document.uploaded_by == admin_user.id
    assert document.category == DocumentCategory.DOCUMENTS


def test_upload_document_success_docx(client, admin_user, admin_headers, db_session):
    """Test successful document upload with DOCX file

    Validates Requirement 2.1: docx classified as ``documents``
    """
    docx_content = b"PK\x03\x04" + b"Fake DOCX content"

    response = client.post(
        "/api/documents/upload",
        files={"file": (
            "report.docx",
            io.BytesIO(docx_content),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )},
        data={"access_level": AccessLevel.ADMINISTRATORS.value},
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["success"] is True
    assert data["document"]["original_name"] == "report.docx"
    assert data["document"]["category"] == DocumentCategory.DOCUMENTS.value


def test_upload_document_success_script(client, admin_user, admin_headers, db_session):
    """Test successful upload of a script file (.sh) classified as ``scripts``

    Validates Requirements 2.2, 4.1
    """
    sh_content = b"#!/bin/bash\necho hello"

    response = client.post(
        "/api/documents/upload",
        files={"file": ("deploy.sh", io.BytesIO(sh_content), "application/x-sh")},
        data={"access_level": AccessLevel.MEMBERS.value},
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["success"] is True
    assert data["document"]["original_name"] == "deploy.sh"
    assert data["document"]["category"] == DocumentCategory.SCRIPTS.value


def test_upload_document_success_links(client, admin_user, admin_headers, db_session):
    """Test successful upload of a .links file classified as ``links``

    Validates Requirement 2.3
    """
    links_content = b"https://example.com\n"

    response = client.post(
        "/api/documents/upload",
        files={"file": ("bookmarks.links", io.BytesIO(links_content), "text/plain")},
        data={"access_level": AccessLevel.PUBLIC.value},
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["success"] is True
    assert data["document"]["category"] == DocumentCategory.LINKS.value


def test_upload_document_file_too_large(client, admin_user, admin_headers):
    """Test document upload fails when file exceeds size limit

    Validates Requirement 4.3: System validates file size
    """
    large_content = b"x" * (11 * 1024 * 1024)  # 11MB

    response = client.post(
        "/api/documents/upload",
        files={"file": ("large_file.pdf", io.BytesIO(large_content), "application/pdf")},
        data={"access_level": AccessLevel.MEMBERS.value},
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_FILE"
    assert "size" in data["error"]["message"].lower()


def test_upload_document_unmapped_extension(client, admin_user, admin_headers, db_session):
    """Test document upload fails with an extension not in CATEGORY_MAPPING

    Validates Requirement 2.4: Unknown extensions are rejected, no row created
    """
    exe_content = b"MZ\x90\x00" + b"Fake executable"

    response = client.post(
        "/api/documents/upload",
        files={"file": ("malware.exe", io.BytesIO(exe_content), "application/x-msdownload")},
        data={"access_level": AccessLevel.MEMBERS.value},
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_FILE_TYPE"

    # No document row should have been created.
    assert db_session.query(Document).count() == 0


def test_upload_document_non_admin_forbidden(client, member_user, member_headers, db_session):
    """Test document upload fails for non-admin users

    Validates Requirement 3.5: Upload restricted to administrators, no row created
    """
    pdf_content = b"%PDF-1.4\n%Test PDF"

    response = client.post(
        "/api/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        data={"access_level": AccessLevel.MEMBERS.value},
        headers=member_headers
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "ADMIN_ACCESS_REQUIRED"
    assert db_session.query(Document).count() == 0


def test_upload_document_unauthenticated(client):
    """Test document upload fails without authentication"""
    pdf_content = b"%PDF-1.4\n%Test PDF"

    response = client.post(
        "/api/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        data={"access_level": AccessLevel.MEMBERS.value},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_upload_document_all_access_levels(client, admin_user, admin_headers, db_session):
    """Test document upload with all available access levels

    Validates Requirement 5.2: System assigns access permissions
    """
    access_levels = [
        AccessLevel.PUBLIC,
        AccessLevel.MEMBERS,
        AccessLevel.ADMINISTRATORS
    ]

    for access_level in access_levels:
        pdf_content = b"%PDF-1.4\n%Test PDF"
        response = client.post(
            "/api/documents/upload",
            files={"file": (
                f"test_{access_level.value}.pdf",
                io.BytesIO(pdf_content),
                "application/pdf",
            )},
            data={"access_level": access_level.value},
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["document"]["access_level"] == access_level.value


def test_upload_document_empty_file(client, admin_user, admin_headers):
    """Test document upload accepts an empty file with a valid extension"""
    empty_content = b""

    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.pdf", io.BytesIO(empty_content), "application/pdf")},
        data={"access_level": AccessLevel.MEMBERS.value},
        headers=admin_headers
    )

    # Empty file should still be accepted if the extension is valid;
    # validation is on the size limit, not a minimum size.
    assert response.status_code == status.HTTP_201_CREATED


def test_upload_document_special_characters_filename(client, admin_user, admin_headers, db_session):
    """Test document upload with special characters in filename"""
    pdf_content = b"%PDF-1.4\n%Test PDF"

    response = client.post(
        "/api/documents/upload",
        files={"file": (
            "test file (2023) [final].pdf",
            io.BytesIO(pdf_content),
            "application/pdf",
        )},
        data={"access_level": AccessLevel.MEMBERS.value},
        headers=admin_headers
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["document"]["original_name"] == "test file (2023) [final].pdf"
    # Unique filename should be different
    assert data["document"]["filename"] != data["document"]["original_name"]

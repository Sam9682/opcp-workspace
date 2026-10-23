"""Integration tests for the Document Audience Adapter endpoints.

Spec: .kiro/specs/document-audience-adapter (task 8.3)
Feature: document-audience-adapter

Exercises the two authenticated endpoints registered by
``app/document_adapter/router.py`` through the FastAPI ``TestClient`` (the
shared ``client`` fixture in ``conftest.py`` overrides ``get_db`` with the
in-memory SQLite session):

- ``POST /api/document-adapter/adapt``
- ``POST /api/document-adapter/export``

Coverage:
- Both endpoints reject unauthenticated requests (Requirement 5.1 / 1.3). The
  real ``get_current_user`` dependency is left in place; with FastAPI's
  ``HTTPBearer`` an entirely missing ``Authorization`` header yields ``403`` and
  an invalid token yields ``401`` — matching the convention used across the
  existing auth tests.
- ``/adapt`` rejects a disabled provider with ``400 PROVIDER_DISABLED``
  (Requirement 5.5) and a missing source with ``404 DOCUMENT_NOT_FOUND``.
- A representative ``/adapt`` call with the AI provider layer mocked returns the
  adapted content and the source name (Requirement 5.1).
- ``/export`` returns a file whose ``Content-Disposition`` filename encodes the
  sanitized source identity and the selected audience level (Requirements 6.2,
  6.3).

The AI provider and the source-text extraction are mocked so no real AI or file
read occurs; the source ``Document`` row is seeded with a real stored file via
``storage_service`` so the service's source resolution succeeds genuinely.
"""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

from app.auth.token import create_access_token
from app.document_adapter import service as service_module
from app.models import Document, User, UserRole
from app.models.document import AccessLevel, DocumentCategory
from app.services.storage_service import storage_service

ADAPT_URL = "/api/document-adapter/adapt"
EXPORT_URL = "/api/document-adapter/export"
PDF_MIME_TYPE = "application/pdf"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def member_user(db_session):
    """Create a verified member whose JWT the adapter endpoints accept."""
    user = User(
        email="adapter-member@test.com",
        password_hash="hashed_password",
        first_name="Adapter",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def member_headers(member_user):
    """Authorization header carrying a valid access token for ``member_user``."""
    token = create_access_token({"sub": str(member_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def source_document(db_session, member_user):
    """Seed a PDF source document with a real stored file.

    The service resolves the row and reads the stored bytes, so the file must
    exist on disk; the actual text extraction is mocked in the adapt test.
    """
    content = b"%PDF-1.4 fake pdf bytes for the adapter source"
    unique_filename, _ = storage_service.save_file(
        file_content=content,
        original_filename="Network Guide.pdf",
    )

    document = Document(
        filename=unique_filename,
        original_name="Network Guide.pdf",
        mime_type=PDF_MIME_TYPE,
        size=len(content),
        category=DocumentCategory.DOCUMENTS,
        access_level=AccessLevel.MEMBERS,
        uploaded_by=member_user.id,
        download_count=0,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    yield document

    storage_service.delete_file(unique_filename)


# ---------------------------------------------------------------------------
# Unauthenticated access (Requirement 5.1 / 1.3)
# ---------------------------------------------------------------------------

def test_adapt_requires_authentication(client):
    """``POST /adapt`` with no credentials is rejected by the auth dependency."""
    response = client.post(
        ADAPT_URL,
        json={
            "document_id": str(uuid.uuid4()),
            "audience_level": "it_beginner",
            "ai_provider": "shai",
        },
    )

    # HTTPBearer with no Authorization header rejects the request before the
    # endpoint body runs (403 missing credentials / 401 invalid — convention
    # used across the existing auth tests).
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


def test_export_requires_authentication(client):
    """``POST /export`` with no credentials is rejected by the auth dependency."""
    response = client.post(
        EXPORT_URL,
        json={
            "adapted_content": "some adapted content",
            "source_name": "Network Guide.pdf",
            "audience_level": "it_beginner",
            "format": "pdf",
        },
    )

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


def test_adapt_invalid_token_rejected(client):
    """``POST /adapt`` with a malformed bearer token returns 401 INVALID_TOKEN."""
    response = client.post(
        ADAPT_URL,
        json={
            "document_id": str(uuid.uuid4()),
            "audience_level": "it_beginner",
            "ai_provider": "shai",
        },
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# /adapt error paths (Requirement 5.5)
# ---------------------------------------------------------------------------

def test_adapt_provider_disabled_rejected(client, member_headers, source_document):
    """A disabled provider is rejected with 400 PROVIDER_DISABLED.

    ``openai`` defaults to disabled (only ``shai`` is always enabled), so no
    config seeding is needed to exercise the rejection.
    """
    response = client.post(
        ADAPT_URL,
        json={
            "document_id": str(source_document.id),
            "audience_level": "intermediate_a",
            "ai_provider": "openai",
        },
        headers=member_headers,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # The global HTTPException handler unwraps the ErrorResponse detail, so the
    # body is ``{"error": {...}}`` at the top level.
    body = response.json()
    assert body["error"]["code"] == "PROVIDER_DISABLED"


def test_adapt_source_not_found_rejected(client, member_headers):
    """A missing library source is rejected with 404 DOCUMENT_NOT_FOUND."""
    response = client.post(
        ADAPT_URL,
        json={
            "document_id": str(uuid.uuid4()),
            "audience_level": "it_beginner",
            "ai_provider": "shai",
        },
        headers=member_headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    body = response.json()
    assert body["error"]["code"] == "DOCUMENT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Representative /adapt call with a mocked provider (Requirement 5.1)
# ---------------------------------------------------------------------------

def test_adapt_returns_adapted_content_with_mocked_provider(
    client, member_headers, source_document
):
    """A representative adapt call returns the provider answer and source name.

    ``shai`` is always enabled; the provider layer and the text extraction are
    mocked so no real AI call or PDF parse occurs, while the source row and its
    stored file are resolved for real.
    """
    mock_provider = SimpleNamespace(
        query=AsyncMock(
            return_value={"answer": "Rewritten for IT beginners, acronyms defined."}
        )
    )

    with patch.object(service_module, "extract_text", return_value="raw source text"), \
            patch.object(service_module, "get_ai_provider", return_value=mock_provider):
        response = client.post(
            ADAPT_URL,
            json={
                "document_id": str(source_document.id),
                "audience_level": "it_beginner",
                "ai_provider": "shai",
            },
            headers=member_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["adapted_content"] == "Rewritten for IT beginners, acronyms defined."
    assert body["source_name"] == "Network Guide.pdf"
    assert body["audience_level"] == "it_beginner"
    assert body["ai_provider"] == "shai"
    assert body["processing_time"] >= 0.0

    # The mocked provider layer was used (no real AI call), and the extracted
    # source text was passed as the provider ``context``.
    mock_provider.query.assert_awaited_once()
    _, kwargs = mock_provider.query.await_args
    assert kwargs["context"] == "raw source text"


# ---------------------------------------------------------------------------
# /export returns a file whose filename encodes source + audience (Req 6.2, 6.3)
# ---------------------------------------------------------------------------

def test_export_pdf_returns_file_with_encoded_filename(client, member_headers):
    """``/export`` (pdf) returns a PDF attachment named by source + audience."""
    response = client.post(
        EXPORT_URL,
        json={
            "adapted_content": "The adapted content body.",
            "source_name": "Network Guide.pdf",
            "audience_level": "opcp_expert",
            "format": "pdf",
        },
        headers=member_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/pdf"

    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    # Filename encodes the sanitized source stem and the audience level value.
    assert "Network_Guide" in disposition
    assert "opcp_expert" in disposition
    assert disposition.rstrip('"').endswith(".pdf")

    # A real PDF byte stream is returned.
    assert response.content[:5] == b"%PDF-"


def test_export_docx_returns_file_with_encoded_filename(client, member_headers):
    """``/export`` (docx) returns a Word attachment named by source + audience."""
    response = client.post(
        EXPORT_URL,
        json={
            "adapted_content": "The adapted content body.",
            "source_name": "Network Guide.pdf",
            "audience_level": "intermediate_b",
            "format": "docx",
        },
        headers=member_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    assert "Network_Guide" in disposition
    assert "intermediate_b" in disposition
    assert disposition.rstrip('"').endswith(".docx")

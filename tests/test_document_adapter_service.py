"""Unit tests for the Document Audience Adapter orchestration service.

Spec: .kiro/specs/document-audience-adapter (task 7.2)

Validates Requirement 5.1: a representative adapt call returns the adapted
content and the source name, with the AI provider layer mocked.
Validates Requirement 5.3: provider-disabled and source-not-found conditions
raise the expected typed errors (``ProviderDisabledError`` /
``SourceNotFoundError``) carrying their stable ``code`` attributes.

The provider layer is mocked so no real AI call is made; the DB session,
``Document`` query, ``storage_service.get_file_path`` and ``extract_text`` are
stubbed so the service logic can be exercised in isolation. ``build_adaptation
_prompt`` is left real (it is a pure function) so the composition is genuine.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.document_adapter import service as service_module
from app.document_adapter.service import (
    DocumentAdapterService,
    ProviderDisabledError,
    SourceNotFoundError,
)
from app.document_adapter.schemas import AdaptationRequest, AudienceLevel

PDF_MIME_TYPE = "application/pdf"


def _make_document(original_name: str = "Source Guide.pdf") -> SimpleNamespace:
    """Return a minimal stand-in for a ``Document`` row used by the service."""
    return SimpleNamespace(
        id=uuid4(),
        filename="stored-unique-name.pdf",
        original_name=original_name,
        mime_type=PDF_MIME_TYPE,
    )


def _make_db_with_document(document) -> MagicMock:
    """Return a DB session mock whose ``query(...).filter(...).first()`` yields ``document``."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = document
    return db


# ---------------------------------------------------------------------------
# Representative adapt call returns adapted content and source name (Req 5.1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adapt_returns_adapted_content_and_source_name():
    """A representative adapt call returns the provider answer and source name."""
    document = _make_document(original_name="Networking Basics.pdf")
    db = _make_db_with_document(document)
    request = AdaptationRequest(
        document_id=document.id,
        audience_level=AudienceLevel.IT_BEGINNER,
        ai_provider="shai",
    )

    mock_provider = SimpleNamespace(
        query=AsyncMock(return_value={"answer": "Adapted beginner-friendly text"})
    )

    with patch.object(service_module, "is_provider_enabled", return_value=True), \
            patch.object(service_module.storage_service, "get_file_path", return_value="/tmp/stored.pdf"), \
            patch("builtins.open", MagicMock()), \
            patch.object(service_module, "extract_text", return_value="raw source text"), \
            patch.object(service_module, "get_ai_provider", return_value=mock_provider) as get_provider:
        response = await DocumentAdapterService.adapt(db, request)

    # The adapted content is exactly the provider's "answer" and the source name
    # is the resolved document's original_name.
    assert response.adapted_content == "Adapted beginner-friendly text"
    assert response.source_name == "Networking Basics.pdf"
    assert response.audience_level == AudienceLevel.IT_BEGINNER
    assert response.ai_provider == "shai"
    assert response.processing_time >= 0.0

    # The mocked provider layer was used (no real AI call).
    get_provider.assert_called_once_with("shai")
    mock_provider.query.assert_awaited_once()
    # The source text was passed to the provider as context.
    _, kwargs = mock_provider.query.await_args
    assert kwargs["context"] == "raw source text"


# ---------------------------------------------------------------------------
# Provider-disabled raises ProviderDisabledError (Req 5.3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adapt_raises_provider_disabled_when_provider_not_enabled():
    """When the provider is not enabled, ProviderDisabledError (PROVIDER_DISABLED) is raised."""
    document = _make_document()
    db = _make_db_with_document(document)
    request = AdaptationRequest(
        document_id=document.id,
        audience_level=AudienceLevel.INTERMEDIATE_A,
        ai_provider="openai",
    )

    with patch.object(service_module, "is_provider_enabled", return_value=False), \
            patch.object(service_module, "get_ai_provider") as get_provider:
        with pytest.raises(ProviderDisabledError) as exc_info:
            await DocumentAdapterService.adapt(db, request)

    assert exc_info.value.code == "PROVIDER_DISABLED"
    assert exc_info.value.provider_id == "openai"
    # Enablement is enforced before any provider resolution occurs.
    get_provider.assert_not_called()


# ---------------------------------------------------------------------------
# Source-not-found raises SourceNotFoundError (Req 5.3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adapt_raises_source_not_found_for_missing_library_document():
    """A missing library document raises SourceNotFoundError (DOCUMENT_NOT_FOUND)."""
    db = _make_db_with_document(None)  # query returns no row
    request = AdaptationRequest(
        document_id=uuid4(),
        audience_level=AudienceLevel.OPCP_EXPERT,
        ai_provider="kiro",
    )

    with patch.object(service_module, "is_provider_enabled", return_value=True):
        with pytest.raises(SourceNotFoundError) as exc_info:
            await DocumentAdapterService.adapt(db, request)

    assert exc_info.value.code == "DOCUMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_adapt_raises_source_not_found_when_stored_file_missing():
    """A resolved row whose stored file is absent raises FILE_NOT_FOUND."""
    document = _make_document()
    db = _make_db_with_document(document)
    request = AdaptationRequest(
        document_id=document.id,
        audience_level=AudienceLevel.INTERMEDIATE_B,
        ai_provider="shai",
    )

    with patch.object(service_module, "is_provider_enabled", return_value=True), \
            patch.object(service_module.storage_service, "get_file_path", return_value=None):
        with pytest.raises(SourceNotFoundError) as exc_info:
            await DocumentAdapterService.adapt(db, request)

    assert exc_info.value.code == "FILE_NOT_FOUND"

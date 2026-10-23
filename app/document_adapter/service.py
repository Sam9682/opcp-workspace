"""Orchestration service for the Document Audience Adapter feature.

Feature: document-audience-adapter
Validates Requirements 5.1, 5.3, 4.2

Composes the existing building blocks to turn a source document (a library
document referenced by id, or a previously uploaded file referenced by its
stored filename) into an audience-tailored rewrite:

1. Resolve the source ``Document`` row and read its stored bytes + MIME type.
2. Extract plain text with :func:`app.document_adapter.extraction.extract_text`.
3. Build the audience-specific prompt with
   :func:`app.document_adapter.prompts.build_adaptation_prompt`.
4. Call ``get_ai_provider(provider_id).query(question, context, ...)`` directly
   (NOT :meth:`OracleService.ask_oracle`) so adapter runs are **not** persisted
   into the Oracle Q&A history, while still honoring the shared
   :func:`app.oracle.provider_config.is_provider_enabled` admin configuration.

Typed errors (:class:`SourceNotFoundError`, :class:`ProviderDisabledError`) and
the re-exported :class:`UnsupportedSourceError` carry stable ``code`` attributes
the router (task 8.1) maps to ``404``/``400`` responses.
"""
from __future__ import annotations

import time
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.document_adapter.extraction import UnsupportedSourceError, extract_text
from app.document_adapter.prompts import build_adaptation_prompt
from app.document_adapter.schemas import AdaptationRequest, AdaptationResponse, AudienceLevel
from app.logging_config import logger
from app.models.document import Document
from app.oracle.ai_providers import get_ai_provider
from app.oracle.provider_config import is_provider_enabled
from app.services.storage_service import storage_service

# Default generation parameters for adaptation. Adaptation rewrites can be long,
# so a generous token budget is used; temperature is kept moderate for faithful
# rewrites. These mirror the provider contract defaults used elsewhere.
_ADAPT_TEMPERATURE = 0.5
_ADAPT_MAX_TOKENS = 4000

__all__ = [
    "SourceNotFoundError",
    "ProviderDisabledError",
    "UnsupportedSourceError",
    "DocumentAdapterService",
    "adapt_document",
]


class SourceNotFoundError(Exception):
    """Raised when the referenced source document cannot be resolved.

    Covers both a missing library row (``DOCUMENT_NOT_FOUND``) and a resolved
    row whose stored file is absent from storage (``FILE_NOT_FOUND``). Carries a
    stable ``code`` the router maps to a ``404`` response.
    """

    def __init__(self, message: str, code: str = "DOCUMENT_NOT_FOUND") -> None:
        super().__init__(message)
        self.code = code


class ProviderDisabledError(Exception):
    """Raised when the selected AI provider is not enabled.

    Mirrors the Oracle router's provider-enablement behavior. Carries a stable
    ``code`` the router maps to a ``400 PROVIDER_DISABLED`` response.
    """

    code: str = "PROVIDER_DISABLED"

    def __init__(self, provider_id: str, message: Optional[str] = None) -> None:
        self.provider_id = provider_id
        super().__init__(
            message
            or f"The AI provider '{provider_id}' is not enabled"
        )


class DocumentAdapterService:
    """Service for generating audience-tailored document adaptations."""

    @staticmethod
    async def adapt(db: Session, request: AdaptationRequest) -> AdaptationResponse:
        """Generate an audience-tailored adaptation of a source document.

        Enforces provider enablement, resolves and extracts the source text,
        builds the audience prompt, calls the provider layer directly, and
        returns the adapted content with the measured processing time and the
        source's ``original_name``.

        Args:
            db: Database session used to resolve the source and check provider
                enablement.
            request: The validated adaptation request (exactly one source
                reference, an audience level, and a provider id).

        Returns:
            An :class:`AdaptationResponse` with the adapted content, the audience
            level, the provider id, the source ``original_name``, and the
            generation ``processing_time`` in seconds.

        Raises:
            ProviderDisabledError: If the selected provider is not enabled.
            SourceNotFoundError: If the source row or its stored file is missing.
            UnsupportedSourceError: If the source is not a PDF/Word document.
        """
        provider_id = request.ai_provider

        # Enforce provider enablement first (cheap, and avoids reading the
        # source when generation cannot proceed). Mirrors the Oracle router.
        if not is_provider_enabled(db, provider_id):
            logger.warning(
                f"Adaptation rejected: provider '{provider_id}' is not enabled"
            )
            raise ProviderDisabledError(provider_id)

        # Resolve the source document row and read its stored bytes + MIME type.
        document = _resolve_source_document(
            db,
            document_id=request.document_id,
            uploaded_filename=request.uploaded_filename,
        )
        file_bytes = _read_source_bytes(document)

        # Extract text (raises UnsupportedSourceError for non-PDF/Word types),
        # then build the audience-specific prompt. The source text is passed to
        # the provider separately as ``context``.
        source_text = extract_text(file_bytes, document.mime_type)
        question = build_adaptation_prompt(request.audience_level, source_text)

        # Call the provider layer directly so this run is NOT persisted into the
        # Oracle Q&A history (unlike OracleService.ask_oracle).
        start_time = time.perf_counter()
        try:
            provider = get_ai_provider(provider_id)
            result = await provider.query(
                question=question,
                context=source_text,
                temperature=_ADAPT_TEMPERATURE,
                max_tokens=_ADAPT_MAX_TOKENS,
            )
        except Exception as exc:
            logger.error(f"Adaptation generation failed: {str(exc)}")
            raise

        processing_time = time.perf_counter() - start_time
        adapted_content = result["answer"]

        logger.info(
            f"Adaptation generated: source='{document.original_name}', "
            f"audience={request.audience_level.value}, provider={provider_id}, "
            f"processing_time={processing_time:.3f}s"
        )

        return AdaptationResponse(
            adapted_content=adapted_content,
            audience_level=request.audience_level,
            ai_provider=provider_id,
            source_name=document.original_name,
            processing_time=processing_time,
        )


def _resolve_source_document(
    db: Session,
    document_id: Optional[UUID],
    uploaded_filename: Optional[str],
) -> Document:
    """Resolve the source ``Document`` row from a library id or stored filename.

    Both a library selection (``document_id``) and a prior upload
    (``uploaded_filename``, the stored unique filename returned by
    ``POST /api/documents/upload``) reference a row in the ``documents`` table.

    Args:
        db: Database session.
        document_id: Library source id (mutually exclusive with
            ``uploaded_filename``; the request validator guarantees exactly one).
        uploaded_filename: Stored filename of a previously uploaded source.

    Returns:
        The resolved :class:`Document` row.

    Raises:
        SourceNotFoundError: If no matching row exists.
    """
    if document_id is not None:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document is None:
            raise SourceNotFoundError(
                f"Document not found: {document_id}",
                code="DOCUMENT_NOT_FOUND",
            )
        return document

    # uploaded_filename path: exactly one of the two is set (enforced by the
    # AdaptationRequest model validator), so uploaded_filename is present here.
    document = (
        db.query(Document)
        .filter(Document.filename == uploaded_filename)
        .first()
    )
    if document is None:
        raise SourceNotFoundError(
            f"Uploaded source not found: {uploaded_filename}",
            code="FILE_NOT_FOUND",
        )
    return document


def _read_source_bytes(document: Document) -> bytes:
    """Read the stored bytes for a resolved source ``Document``.

    Args:
        document: The resolved source row.

    Returns:
        The raw file bytes.

    Raises:
        SourceNotFoundError: If the stored file is absent from storage.
    """
    file_path = storage_service.get_file_path(document.filename)
    if not file_path:
        raise SourceNotFoundError(
            f"Source file not found in storage: {document.filename}",
            code="FILE_NOT_FOUND",
        )
    with open(file_path, "rb") as f:
        return f.read()


async def adapt_document(db: Session, request: AdaptationRequest) -> AdaptationResponse:
    """Module-level convenience wrapper around :meth:`DocumentAdapterService.adapt`."""
    return await DocumentAdapterService.adapt(db, request)

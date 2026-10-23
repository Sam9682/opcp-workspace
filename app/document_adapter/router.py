"""Document Audience Adapter API endpoints.

Feature: document-audience-adapter
Validates Requirements 5.1, 5.3, 5.5, 6.2, 6.3, 6.4

Exposes two authenticated endpoints:

- ``POST /api/document-adapter/adapt`` rewrites a source document (a library
  document by id, or a previously uploaded file by its stored filename) for a
  selected audience level using the chosen AI provider. Typed service errors
  are mapped to the shared :meth:`ErrorResponse.create` envelope
  (``400 INVALID_FILE_TYPE``, ``400 PROVIDER_DISABLED``,
  ``404 DOCUMENT_NOT_FOUND`` / ``FILE_NOT_FOUND``,
  ``502 PROVIDER_AUTH_ERROR`` when the upstream provider rejects our
  credentials, ``500`` otherwise).
- ``POST /api/document-adapter/export`` renders adapted content into a
  downloadable PDF or Word file with a ``Content-Disposition`` filename encoding
  the source identity and the audience level.

Both endpoints require an authenticated user via ``get_current_user``.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas import ErrorResponse
from app.database import get_db
from app.document_adapter.export import (
    build_export_filename,
    render_docx,
    render_pdf,
)
from app.document_adapter.schemas import (
    AdaptationRequest,
    AdaptationResponse,
    ExportRequest,
)
from app.document_adapter.service import (
    DocumentAdapterService,
    ProviderAuthError,
    ProviderDisabledError,
    SourceNotFoundError,
    UnsupportedSourceError,
)
from app.logging_config import logger
from app.models.user import User

router = APIRouter(prefix="/api/document-adapter", tags=["document-adapter"])

# Media type for each supported export format.
_PDF_MEDIA_TYPE = "application/pdf"
_DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@router.post(
    "/adapt",
    response_model=AdaptationResponse,
    summary="Adapt a source document for a target audience",
    description="""
    Rewrite a source document (PDF or Word) for the selected audience level
    using the chosen AI provider.

    Validates Requirements 5.1, 5.3, 5.5:
    - Exactly one source reference (library document id or uploaded filename)
    - Provider must be enabled (admin configuration)
    - Returns the adapted content, source name, and processing time

    Requires an authenticated user.
    """,
)
async def adapt_document(
    request: AdaptationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdaptationResponse:
    """Generate an audience-tailored adaptation of a source document.

    Validates Requirements 5.1, 5.3, 5.5:
    - Delegates orchestration to :meth:`DocumentAdapterService.adapt`
    - Maps typed service errors to the shared error envelope with stable codes

    Args:
        request: Validated adaptation request (one source reference, an audience
            level, and a provider id).
        current_user: Authenticated user (required).
        db: Database session.

    Returns:
        AdaptationResponse with the adapted content and metadata.

    Raises:
        HTTPException 400: INVALID_FILE_TYPE (unsupported source) or
            PROVIDER_DISABLED (provider not enabled).
        HTTPException 404: DOCUMENT_NOT_FOUND / FILE_NOT_FOUND (source missing).
        HTTPException 502: PROVIDER_AUTH_ERROR (upstream provider rejected the
            configured credentials, HTTP 401/403).
        HTTPException 500: For any other failure.
    """
    logger.info(
        f"Document adaptation requested by user {current_user.id}: "
        f"audience={request.audience_level.value}, provider={request.ai_provider}"
    )

    try:
        return await DocumentAdapterService.adapt(db, request)
    except UnsupportedSourceError as exc:
        logger.warning(f"Adaptation rejected (unsupported source): {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code=exc.code,
                message=str(exc),
                details={},
            ),
        )
    except ProviderDisabledError as exc:
        logger.warning(f"Adaptation rejected (provider disabled): {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code=exc.code,
                message=str(exc),
                details={"provider_id": exc.provider_id},
            ),
        )
    except SourceNotFoundError as exc:
        logger.warning(f"Adaptation rejected (source not found): {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code=exc.code,
                message=str(exc),
                details={},
            ),
        )
    except ProviderAuthError as exc:
        # Upstream provider rejected our credentials (HTTP 401/403). This is a
        # configuration/upstream fault, not an internal server error, so map it
        # to 502 Bad Gateway with a clear French message and NO stack trace
        # (logged as a concise warning in the service layer).
        logger.warning(
            f"Adaptation rejected (provider auth error): {str(exc)}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse.create(
                code=exc.code,
                message=(
                    "Le service d'IA a refusé les identifiants configurés. "
                    "Veuillez vérifier la clé d'API du fournisseur ou "
                    "réessayer avec un autre fournisseur."
                ),
                details={"provider_id": exc.provider_id},
            ),
        )
    except Exception as exc:
        logger.error(f"Adaptation failed: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="ADAPTATION_ERROR",
                message="Failed to adapt the document",
                details={"error": str(exc)},
            ),
        )


@router.post(
    "/export",
    summary="Export adapted content as a downloadable file",
    description="""
    Render adapted content into a downloadable PDF or Word file.

    Validates Requirements 6.2, 6.3, 6.4:
    - Renders via reportlab (PDF) or python-docx (Word)
    - Returns a binary response with a Content-Disposition attachment filename
      encoding the source identity and the audience level

    Requires an authenticated user.
    """,
)
async def export_adapted(
    request: ExportRequest,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Render adapted content into a downloadable PDF or Word file.

    Validates Requirements 6.2, 6.3, 6.4:
    - Selects the renderer and media type from ``request.format``
    - Builds the filename with :func:`build_export_filename`
    - Returns the rendered bytes as an attachment

    Args:
        request: Validated export request (content, source name, audience level,
            and format).
        current_user: Authenticated user (required).

    Returns:
        A binary Response with the rendered file and a Content-Disposition
        attachment header.

    Raises:
        HTTPException 500: If rendering fails.
    """
    logger.info(
        f"Adapted-content export requested by user {current_user.id}: "
        f"format={request.format}, audience={request.audience_level.value}"
    )

    try:
        if request.format == "docx":
            file_bytes = render_docx(request.adapted_content)
            media_type = _DOCX_MEDIA_TYPE
        else:
            file_bytes = render_pdf(request.adapted_content)
            media_type = _PDF_MEDIA_TYPE
    except Exception as exc:
        logger.error(f"Export rendering failed: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="EXPORT_ERROR",
                message="Failed to render the adapted content for export",
                details={"error": str(exc), "format": request.format},
            ),
        )

    filename = build_export_filename(
        request.source_name,
        request.audience_level,
        request.format,
    )

    logger.info(f"Serving adapted-content export: {filename}")

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
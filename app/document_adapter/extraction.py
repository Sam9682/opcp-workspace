"""Source text extraction for the Document Audience Adapter feature.

Reads a source document (PDF or Word) from raw bytes and returns plain text.
PDF text is extracted with ``pypdf`` (already a dependency); Word text is
extracted with ``python-docx``. Any non-PDF/Word MIME type raises the typed
``UnsupportedSourceError`` so the router can map it to a ``400 INVALID_FILE_TYPE``
response.

Feature: document-audience-adapter
Validates Requirements 2.3, 2.4
"""
from __future__ import annotations

import io

# Supported source MIME types: PDF, legacy Word (.doc), and Word OpenXML (.docx).
SUPPORTED_SOURCE_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_PDF_MIME_TYPE = "application/pdf"
_WORD_MIME_TYPES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class UnsupportedSourceError(Exception):
    """Raised when a source document is not a supported PDF/Word type.

    Carries a stable ``code`` the router maps to ``400 INVALID_FILE_TYPE`` and
    the frontend maps to a localized message.
    """

    code: str = "INVALID_FILE_TYPE"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


def is_supported_source_type(mime_type: str) -> bool:
    """Return ``True`` iff ``mime_type`` is one of the supported source types.

    Supported types are exactly PDF (``application/pdf``), legacy Word
    (``application/msword``), and Word OpenXML
    (``application/vnd.openxmlformats-officedocument.wordprocessingml.document``).
    """
    return mime_type in SUPPORTED_SOURCE_MIME_TYPES


def extract_text(file_bytes: bytes, mime_type: str) -> str:
    """Return plain text for a PDF or Word document.

    Args:
        file_bytes: The raw bytes of the source document.
        mime_type: The MIME type identifying the source format.

    Returns:
        The extracted plain text, with page/paragraph content joined by newlines.

    Raises:
        UnsupportedSourceError: If ``mime_type`` is not a supported PDF/Word type.
    """
    if not is_supported_source_type(mime_type):
        raise UnsupportedSourceError(
            f"Unsupported source MIME type: {mime_type!r}. "
            "Accepted formats are PDF and Word."
        )

    if mime_type == _PDF_MIME_TYPE:
        return _extract_pdf_text(file_bytes)

    if mime_type in _WORD_MIME_TYPES:
        return _extract_word_text(file_bytes)

    # Unreachable: the membership check above covers every supported type.
    raise UnsupportedSourceError(
        f"Unsupported source MIME type: {mime_type!r}. "
        "Accepted formats are PDF and Word."
    )


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using ``pypdf``."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _extract_word_text(file_bytes: bytes) -> str:
    """Extract text from Word (.docx) bytes using ``python-docx``.

    ``python-docx`` is added to ``requirements.txt`` in a later task; the import
    is kept local and failures are surfaced as a clear runtime error so the rest
    of the module (and the PDF path) remains importable without the dependency.
    """
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover - exercised only without the dep
        raise RuntimeError(
            "python-docx is required to extract text from Word documents. "
            "Install 'python-docx' (see requirements.txt)."
        ) from exc

    document = docx.Document(io.BytesIO(file_bytes))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    return "\n".join(paragraphs).strip()

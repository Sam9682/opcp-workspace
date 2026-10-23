"""Unit tests for Document Audience Adapter source text extraction.

Spec: .kiro/specs/document-audience-adapter (task 2.3)

Validates Requirement 2.3: ``extract_text`` reads a PDF or Word source document
from raw bytes and returns its plain text.
Validates Requirement 2.4: an unsupported MIME type raises the typed
``UnsupportedSourceError``.

Rather than committing binary fixtures, the PDF fixture is generated at test
time with ``reportlab`` and the Word fixture with ``python-docx`` (both already
installed), each carrying known text that must survive extraction.
"""
import io

import pytest

from app.document_adapter.extraction import (
    UnsupportedSourceError,
    extract_text,
)

PDF_MIME_TYPE = "application/pdf"
DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

KNOWN_PDF_TEXT = "Audience adapter PDF fixture content"
KNOWN_DOCX_FIRST_LINE = "Audience adapter Word fixture content"
KNOWN_DOCX_SECOND_LINE = "second paragraph of the fixture"


def _build_pdf_bytes(text: str) -> bytes:
    """Return the bytes of a one-page PDF containing ``text`` (via reportlab)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    return buffer.getvalue()


def _build_docx_bytes(*paragraphs: str) -> bytes:
    """Return the bytes of a .docx document with the given paragraphs (python-docx)."""
    import docx

    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# PDF and Word extraction return the expected text (Requirement 2.3)
# ---------------------------------------------------------------------------

def test_extract_text_returns_pdf_content():
    """extract_text on PDF bytes returns the embedded known text."""
    pdf_bytes = _build_pdf_bytes(KNOWN_PDF_TEXT)

    text = extract_text(pdf_bytes, PDF_MIME_TYPE)

    assert text.strip(), "extracted PDF text should be non-empty"
    assert KNOWN_PDF_TEXT in text


def test_extract_text_returns_word_content():
    """extract_text on .docx bytes returns the paragraph text, newline-joined."""
    docx_bytes = _build_docx_bytes(KNOWN_DOCX_FIRST_LINE, KNOWN_DOCX_SECOND_LINE)

    text = extract_text(docx_bytes, DOCX_MIME_TYPE)

    assert KNOWN_DOCX_FIRST_LINE in text
    assert KNOWN_DOCX_SECOND_LINE in text
    # Paragraphs are joined by newlines, preserving document order.
    assert text.index(KNOWN_DOCX_FIRST_LINE) < text.index(KNOWN_DOCX_SECOND_LINE)


# ---------------------------------------------------------------------------
# Unsupported MIME type raises UnsupportedSourceError (Requirement 2.4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "unsupported_mime_type",
    ["text/plain", "image/png", "application/json", "", "application/pdf;charset=utf-8"],
)
def test_extract_text_rejects_unsupported_mime_type(unsupported_mime_type):
    """A non-PDF/Word MIME type raises the typed UnsupportedSourceError."""
    with pytest.raises(UnsupportedSourceError) as exc_info:
        extract_text(b"irrelevant bytes", unsupported_mime_type)

    # The typed error carries the stable INVALID_FILE_TYPE code and names the
    # accepted formats so the router/frontend can surface a clear message.
    assert exc_info.value.code == "INVALID_FILE_TYPE"
    assert "PDF and Word" in str(exc_info.value)

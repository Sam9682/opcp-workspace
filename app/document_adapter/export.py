"""Export rendering and filename construction for the Document Audience Adapter.

Feature: document-audience-adapter
Validates Requirements 6.2, 6.3

Pure rendering helpers that turn adapted text into a downloadable PDF
(``reportlab``) or Word (``python-docx``) byte stream, plus the filename
builder that encodes both the source identity and the selected audience level.

``render_docx`` imports ``python-docx`` lazily so this module remains importable
in environments where that optional dependency is not yet installed (it is added
by a later task); PDF rendering and filename construction have no such
dependency.
"""
import io
import re
from typing import Union

from app.document_adapter.schemas import AudienceLevel

__all__ = ["render_pdf", "render_docx", "build_export_filename"]

# File extension for each supported export format.
_FORMAT_EXTENSIONS = {"pdf": "pdf", "docx": "docx"}

# Characters allowed in the sanitized source stem; everything else is replaced.
_INVALID_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_REPEATED_UNDERSCORES = re.compile(r"_+")


def render_pdf(adapted_content: str) -> bytes:
    """Render ``adapted_content`` into a PDF document and return its bytes.

    Each line of the adapted content becomes a paragraph; blank lines become
    vertical spacing so the original paragraph structure is preserved. The text
    round-trips: extracting the text back out of the PDF yields the adapted
    content (Correctness Property 9).
    """
    # Imported here (rather than at module load) to keep import cost local to
    # the rendering path and mirror the lazy pattern used for Word export.
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "AdaptedBody",
        parent=styles["Normal"],
        fontSize=11,
        leading=15,
    )

    story = []
    for line in adapted_content.split("\n"):
        if line.strip():
            # Escape XML-significant characters so reportlab renders the text
            # literally rather than interpreting it as inline markup.
            story.append(Paragraph(escape(line), body_style))
        else:
            story.append(Spacer(1, 6))

    if not story:
        # SimpleDocTemplate requires at least one flowable to build a page.
        story.append(Spacer(1, 1))

    doc.build(story)
    return buffer.getvalue()


def render_docx(adapted_content: str) -> bytes:
    """Render ``adapted_content`` into a Word (.docx) document and return bytes.

    Each line of the adapted content becomes its own paragraph, preserving the
    original line structure. ``python-docx`` is imported lazily so the module is
    importable even when that dependency is not installed.
    """
    from docx import Document  # lazy import: python-docx is an optional dep

    document = Document()
    for line in adapted_content.split("\n"):
        document.add_paragraph(line)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def build_export_filename(
    source_name: str,
    audience: Union[AudienceLevel, str],
    fmt: str,
) -> str:
    """Build the export filename encoding the source identity and audience.

    Convention::

        {sanitized_source_stem}__{audience_level}.{ext}

    - ``sanitized_source_stem``: ``source_name`` with its extension stripped and
      every run of non-``[A-Za-z0-9._-]`` characters replaced by a single ``_``;
      falls back to ``document`` when the result is empty.
    - ``audience_level``: the enum value (e.g. ``it_beginner``).
    - ``ext``: ``pdf`` or ``docx`` (defaults to ``pdf`` for unknown formats).

    Example: ``Network Guide.pdf`` + ``opcp_expert`` + ``pdf`` ->
    ``Network_Guide__opcp_expert.pdf``.
    """
    stem = _sanitize_source_stem(source_name)
    audience_value = audience.value if isinstance(audience, AudienceLevel) else str(audience)
    ext = _FORMAT_EXTENSIONS.get(fmt, "pdf")
    return f"{stem}__{audience_value}.{ext}"


def _sanitize_source_stem(source_name: str) -> str:
    """Strip the extension from ``source_name`` and sanitize the stem.

    Non-``[A-Za-z0-9._-]`` character runs become a single ``_``; leading and
    trailing ``_`` are trimmed; an empty result falls back to ``document``.
    """
    name = source_name or ""
    # Strip a trailing extension (text after the last dot) if one exists.
    dot = name.rfind(".")
    stem = name[:dot] if dot > 0 else name

    sanitized = _INVALID_FILENAME_CHARS.sub("_", stem)
    sanitized = _REPEATED_UNDERSCORES.sub("_", sanitized)
    sanitized = sanitized.strip("_")

    return sanitized or "document"

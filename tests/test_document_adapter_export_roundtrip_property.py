"""Property-based test for Document Audience Adapter export round-trip.

Feature: document-audience-adapter
Property 9: Exported files round-trip the adapted content.
    Validates: Requirements 6.2

For any adapted-content text, ``render_pdf`` (app/document_adapter/export.py)
followed by extracting the text back out of the produced PDF (via ``pypdf``)
yields text that contains the adapted content.

PDF text extraction normalizes whitespace (line breaks and runs of spaces are
not faithfully preserved) and some glyphs extract unreliably, so the Hypothesis
strategy is constrained to a sensible printable-text domain: words of ASCII
letters and digits joined by single spaces. The round-trip assertion then
compares on a whitespace-normalized basis, which keeps the property meaningful
and stable while still exercising >= 100 generated cases.
"""
import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pypdf import PdfReader
import io

from app.document_adapter.export import render_pdf


# A single "word": one or more ASCII letters/digits. These characters extract
# faithfully from the default reportlab (Helvetica) font, unlike punctuation,
# whitespace (which PDF text extraction normalizes or drops) or exotic Unicode
# glyphs (which the base-14 fonts cannot encode and which extract as a
# replacement glyph). Constraining to ASCII letters and digits keeps the
# round-trip assertion meaningful and stable, per the task's printable-text
# domain guidance.
_ASCII_ALNUM = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
)
_word = st.text(alphabet=_ASCII_ALNUM, min_size=1, max_size=12)

# Adapted content: a non-empty sequence of words joined by single spaces. This
# is the sensible printable-text domain over which the round-trip is stable.
_adapted_content = st.lists(_word, min_size=1, max_size=20).map(" ".join)


def _normalize(text: str) -> str:
    """Collapse all runs of whitespace to single spaces and strip the ends.

    PDF extraction does not preserve the exact whitespace of the source, so both
    the original adapted content and the extracted text are normalized this way
    before the containment check.
    """
    return re.sub(r"\s+", " ", text).strip()


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract and concatenate the text from every page of ``pdf_bytes``."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


@pytest.mark.property
@settings(max_examples=150)
@given(adapted_content=_adapted_content)
def test_render_pdf_round_trips_adapted_content(adapted_content):
    """Property 9: Exported files round-trip the adapted content.

    Feature: document-audience-adapter, Property 9: Exported files round-trip
    the adapted content.
    Validates: Requirements 6.2.
    """
    pdf_bytes = render_pdf(adapted_content)

    # render_pdf always produces a non-empty PDF byte stream.
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")

    extracted = _extract_pdf_text(pdf_bytes)

    # The adapted content survives the PDF round-trip (modulo whitespace
    # normalization inherent to PDF text extraction).
    assert _normalize(adapted_content) in _normalize(extracted), (
        "adapted content not found in extracted PDF text\n"
        f"  adapted : {_normalize(adapted_content)!r}\n"
        f"  extracted: {_normalize(extracted)!r}"
    )

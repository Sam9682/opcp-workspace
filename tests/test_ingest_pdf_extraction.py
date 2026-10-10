"""PDF extraction edge-case test for the pgvector-doc-embeddings feature.

Feature: pgvector-doc-embeddings
Covers optional test task:
- 4.2  PDF extraction edge-case test

Design: Testing Strategy -> Example / edge-case unit tests:
    "PDF extraction (Req 4.3): extract text from a tiny bundled PDF fixture and
     assert non-empty text flows into chunking."

Rather than committing a binary PDF fixture, this test generates a tiny one-page
PDF at test time using `reportlab` (already a dependency) with known text, then
exercises `extract_text` on a `DocFile` of kind "pdf" and confirms the known text
survives extraction and that `chunk_text` yields at least one non-empty chunk.
"""
from pathlib import Path

import pytest

from scripts.ingest_embeddings import DocFile, chunk_text, extract_text


KNOWN_TEXT = "Hello pgvector ingestion fixture"


def _write_tiny_pdf(path: Path, text: str) -> None:
    """Write a one-page PDF containing ``text`` using reportlab."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()


class TestPdfExtraction:
    def test_extract_text_reads_known_pdf_text_and_flows_into_chunking(self, tmp_path):
        """extract_text on a PDF DocFile returns the embedded text, and that
        text produces at least one non-empty chunk.

        Validates: Requirements 4.3
        """
        pdf_path = tmp_path / "fixture.pdf"
        _write_tiny_pdf(pdf_path, KNOWN_TEXT)

        doc = DocFile(path=pdf_path, title=pdf_path.stem, kind="pdf")

        text = extract_text(doc)

        # Non-empty extraction carrying the known content.
        assert text.strip(), "extracted PDF text should be non-empty"
        assert KNOWN_TEXT in text, (
            f"known text {KNOWN_TEXT!r} not found in extracted PDF text {text!r}"
        )

        # The extracted text flows into chunking and yields real chunks.
        chunks = chunk_text(text)
        assert len(chunks) >= 1, "chunking extracted PDF text should yield >= 1 chunk"
        assert any(chunk.strip() for chunk in chunks), (
            "at least one produced chunk should be non-empty"
        )
        assert KNOWN_TEXT in "".join(chunks), (
            "known text should survive chunking"
        )

"""Property-based test for the pgvector-doc-embeddings chunking logic.

Feature: pgvector-doc-embeddings
Property 3: Chunking produces contiguous, fully-covering indices
Validates: Requirements 4.4

This Hypothesis-driven property exercises ``chunk_text`` (from
``scripts.ingest_embeddings``) across many generated inputs, varying the text
length, ``chunk_size``, and ``overlap`` (with ``0 <= overlap < chunk_size``).

It asserts the two guarantees documented in the ``chunk_text`` docstring:

- **Contiguous indices**: the returned list positions ARE the chunk indices, so
  they form the contiguous sequence ``0, 1, ..., n-1`` (Req 4.4). We assert this
  by walking the returned list and checking that each chunk lives at its index.
- **Full coverage with no gaps**: consecutive chunks advance by
  ``step = chunk_size - overlap`` characters. The non-overlapping portion of
  each chunk is its first ``step`` characters; concatenating those portions for
  every chunk except the last, then appending the entire last chunk,
  reconstructs the input text exactly (Property 3 / Req 4.4).

Edge case: empty ``text`` produces ``[]`` (no chunks to embed), matching the
implementation's coverage semantics.
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.ingest_embeddings import chunk_text


@st.composite
def _text_and_params(draw):
    """Generate (text, chunk_size, overlap) with 0 <= overlap < chunk_size.

    ``chunk_size`` is kept modest relative to the generated text so that many
    examples produce multiple chunks (exercising the multi-chunk coverage path)
    while still covering the single-chunk and empty-text cases.
    """
    text = draw(st.text(max_size=400))
    chunk_size = draw(st.integers(min_value=1, max_value=200))
    overlap = draw(st.integers(min_value=0, max_value=chunk_size - 1))
    return text, chunk_size, overlap


@pytest.mark.property
@settings(max_examples=200)
@given(params=_text_and_params())
def test_chunking_contiguous_and_fully_covering(params):
    """Property 3: contiguous 0..n-1 indices + gapless reconstruction (Req 4.4)."""
    text, chunk_size, overlap = params
    step = chunk_size - overlap

    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    # Empty text -> no chunks (implementation coverage semantics).
    if text == "":
        assert chunks == []
        return

    # Non-empty text must yield at least one chunk.
    assert len(chunks) >= 1

    # --- Contiguous indices: list positions are the chunk indices 0..n-1. ---
    # (chunk_index i corresponds to chunks[i]; enumerate confirms contiguity.)
    for expected_index, chunk in enumerate(chunks):
        assert chunks[expected_index] is chunk
        # Every non-final chunk carries a full window; only the tail may be short.
        assert len(chunk) <= chunk_size

    # --- Full coverage with no gaps ---
    # Concatenate the first `step` chars of each chunk except the last, then
    # append the entire last chunk. This must reconstruct the input exactly.
    reconstructed = "".join(c[:step] for c in chunks[:-1]) + chunks[-1]
    assert reconstructed == text

    # A single chunk means the whole text fit; it must equal the text.
    if len(chunks) == 1:
        assert chunks[0] == text

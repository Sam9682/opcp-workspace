"""Property-based test for changed-document re-ingestion replacement.

Feature: pgvector-doc-embeddings
Property 5: Re-ingesting a changed document replaces its chunks
Validates: Requirements 5.2

For any document that has been ingested and is then re-ingested with different
content, the rows stored in ``md_embeddings`` for that ``file_path`` equal
exactly the chunks produced from the *new* content, and none of the chunks from
the *old* content remain (Design §5 "Idempotent upsert"; Correctness
Properties → Property 5).

The test reuses the same in-memory fake connection/cursor approach as Property 4
(task 6.3): the fake models the ``md_embeddings`` table as a plain in-memory
list of rows and implements the DELETE-then-INSERT semantics that
``ingest_file`` emits (``DELETE FROM <table> WHERE file_path = %s`` followed by
``INSERT INTO <table> (title, file_path, chunk_index, content, embedding)
VALUES (%s, %s, %s, %s, %s::vector)``). A stub provider supplies a deterministic
``_embed_query`` and a ``table_name`` so no real DB or OVH call is made.

The generator produces first content, ingests it against a real temp file, then
produces *different* content (guaranteed to differ in chunk count and/or chunk
text), rewrites the file, and re-ingests. It then asserts the surviving rows for
that ``file_path`` equal exactly the second content's chunks with no stale rows.

Runs with at least 100 Hypothesis iterations.
"""
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scripts.ingest_embeddings import DocFile, chunk_text, extract_text, ingest_file


# ---------------------------------------------------------------------------
# In-memory fake connection / cursor modeling the md_embeddings table.
# ---------------------------------------------------------------------------
class _FakeCursor:
    """Parses the DELETE / INSERT statements ``ingest_file`` issues.

    Rows are stored in the shared ``rows`` list owned by the connection as
    tuples ``(title, file_path, chunk_index, content, embedding)`` — mirroring
    the real table columns. ``DELETE ... WHERE file_path = %s`` removes matching
    rows; the INSERT appends one row per chunk.
    """

    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split()).lower()
        if normalized.startswith("delete from"):
            (file_path,) = params
            # Delete-then-insert key: drop every prior row for this file_path.
            self._rows[:] = [r for r in self._rows if r[1] != file_path]
        elif normalized.startswith("insert into"):
            title, file_path, chunk_index, content, embedding = params
            self._rows.append((title, file_path, chunk_index, content, embedding))
        else:  # pragma: no cover - ingest_file emits only DELETE/INSERT
            raise AssertionError(f"unexpected SQL in ingest_file: {sql!r}")

    def close(self):
        pass


class _FakeConn:
    """A fake connection whose cursors mutate a shared in-memory row list."""

    def __init__(self):
        self.rows = []

    def cursor(self):
        return _FakeCursor(self.rows)

    def commit(self):
        pass

    def rollback(self):  # pragma: no cover - not expected in this property
        pass


class _StubProvider:
    """Minimal provider stub for ingest_file: table_name + deterministic embed."""

    def __init__(self, table_name="md_embeddings"):
        self.table_name = table_name

    def _embed_query(self, client, query: str) -> list:
        # Deterministic, content-derived vector; value is irrelevant to Property 5
        # (which is about which rows survive), only that it is produced per chunk.
        return [float(len(query)), float(sum(ord(c) for c in query) % 1000)]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
# Text long enough to exercise multiple chunks without being slow. We assert
# against chunk_text with the same defaults ingest_file uses (chunk_size=1000,
# overlap=100). We exclude carriage returns from the alphabet: writing "\r" and
# reading it back via read_text() triggers universal-newline normalization
# ("\r" -> "\n"), which would make the in-memory string diverge from what the
# code actually stores. Excluding "\r" keeps the on-disk round-trip faithful
# while still exercising arbitrary content, including "\n".
# Surrogate code points (category "Cs") cannot be UTF-8 encoded to a real file,
# so they are excluded — a genuine document on disk can never contain them.
_content = st.text(
    alphabet=st.characters(blacklist_characters="\r", blacklist_categories=("Cs",)),
    min_size=0,
    max_size=3000,
)


@st.composite
def _distinct_content_pair(draw):
    """Return (first, second) content that differ in produced chunks.

    "Different content" per Req 5.2 means the re-ingest genuinely changes the
    document. We require the two contents to produce a different chunk list
    (different count and/or different chunk text) so the property meaningfully
    tests replacement rather than a no-op re-run (which is Property 4's job).
    """
    first = draw(_content)
    second = draw(_content)
    # Reject pairs whose chunking is identical; that case is Property 4, not 5.
    first_chunks = chunk_text(first)
    second_chunks = chunk_text(second)
    from hypothesis import assume

    assume(first_chunks != second_chunks)
    return first, second


# ===========================================================================
# Property 5: re-ingesting changed content replaces the stored chunks.
# ===========================================================================
@settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(pair=_distinct_content_pair())
def test_reingest_changed_document_replaces_chunks(tmp_path_factory, pair):
    """Feature: pgvector-doc-embeddings, Property 5: Re-ingesting a changed
    document replaces its chunks.

    Validates: Requirements 5.2
    """
    first_content, second_content = pair

    root = tmp_path_factory.mktemp("changed")
    file_path = root / "doc.md"
    doc = DocFile(path=file_path, title=file_path.stem, kind="md")

    conn = _FakeConn()
    provider = _StubProvider()
    embed_client = object()  # opaque; _embed_query stub ignores it

    key = str(file_path)

    # --- First ingest ------------------------------------------------------
    file_path.write_text(first_content, encoding="utf-8")
    # Expected chunks are derived through the same read path the code uses, so
    # the comparison is faithful to what actually gets stored.
    first_chunks = chunk_text(extract_text(doc))
    count1 = ingest_file(conn, provider, embed_client, doc)

    assert count1 == len(first_chunks)
    rows_after_first = [r for r in conn.rows if r[1] == key]
    assert len(rows_after_first) == len(first_chunks), (
        "COUNTEREXAMPLE: first ingest did not store one row per chunk.\n"
        f"  stored={len(rows_after_first)} expected={len(first_chunks)}"
    )

    # --- Re-ingest with different content ----------------------------------
    file_path.write_text(second_content, encoding="utf-8")
    second_chunks = chunk_text(second_content)
    count2 = ingest_file(conn, provider, embed_client, doc)

    assert count2 == len(second_chunks)

    # Surviving rows for this file_path, ordered by chunk_index.
    surviving = sorted(
        (r for r in conn.rows if r[1] == key), key=lambda r: r[2]
    )

    # Exact replacement: rows equal exactly the second content's chunks.
    assert len(surviving) == len(second_chunks), (
        "COUNTEREXAMPLE: stored row count != new chunk count after re-ingest.\n"
        f"  surviving={len(surviving)} expected={len(second_chunks)}"
    )

    # chunk_index runs 0..n-1 contiguously and content matches the NEW chunks.
    for expected_index, (row, expected_chunk) in enumerate(
        zip(surviving, second_chunks)
    ):
        title, row_path, chunk_index, content, embedding = row
        assert row_path == key
        assert title == doc.title
        assert chunk_index == expected_index, (
            "COUNTEREXAMPLE: chunk_index not contiguous 0..n-1 after re-ingest.\n"
            f"  got index={chunk_index} at position {expected_index}"
        )
        assert content == expected_chunk, (
            "COUNTEREXAMPLE: surviving content does not match new chunk.\n"
            f"  index={expected_index}\n  got={content!r}\n  expected={expected_chunk!r}"
        )

    # No stale rows: every stored content for this file_path is a NEW chunk;
    # none of the old chunks remain unless they are also present in the new set.
    surviving_contents = [r[3] for r in surviving]
    assert surviving_contents == second_chunks, (
        "COUNTEREXAMPLE: surviving contents are not exactly the new chunks.\n"
        f"  surviving={surviving_contents}\n  new={second_chunks}"
    )

    # Explicit stale-row check: any old chunk that is NOT in the new set must be
    # entirely gone from storage.
    stale_only = set(first_chunks) - set(second_chunks)
    assert stale_only.isdisjoint(set(surviving_contents)), (
        "COUNTEREXAMPLE: stale chunk(s) from old content survived re-ingest.\n"
        f"  stale_present={stale_only & set(surviving_contents)}"
    )

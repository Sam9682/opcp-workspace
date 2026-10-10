"""Property-based test for re-run idempotency of the ingestion upsert.

Feature: pgvector-doc-embeddings
Property 4: Ingestion is idempotent over re-runs (no duplicate rows)
Validates: Requirements 5.1

For any set of source documents, ingesting them once and then ingesting the same
unchanged set again yields a ``md_embeddings`` table with no duplicate rows for
the same ``(file_path, chunk_index)`` combination — running the ingestion twice
produces the same row set as running it once (Design §5 "Idempotent upsert";
Correctness Properties → Property 4).

Strategy
--------
Rather than mock at the SQL-string level, this test builds a *fake connection*
that actually models the ``md_embeddings`` table as an in-memory row store and
applies the real delete-then-insert semantics that ``ingest_file`` issues:

- ``DELETE FROM <table> WHERE file_path = %s`` removes every row whose
  ``file_path`` equals the bound parameter.
- ``INSERT INTO <table> (title, file_path, chunk_index, content, embedding)
  VALUES (%s, %s, %s, %s, %s::vector)`` appends one row built from the bound
  parameters.

``ingest_file`` reads the documents end-to-end from real temp files (so
``extract_text`` and ``chunk_text`` run for real), embeds each chunk through a
deterministic provider stub (``_embed_query`` + ``table_name``), and writes
through the fake connection.

We ingest a generated doc set once, snapshot the row store, ingest the exact
same set again, and assert:

- no duplicate ``(file_path, chunk_index)`` rows exist after either run, and
- the two-run row set equals the single-run row set.

Runs with at least 100 Hypothesis iterations.
"""
from __future__ import annotations

import re
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scripts.ingest_embeddings import DocFile, discover_documents, ingest_file


# ---------------------------------------------------------------------------
# Fake DB: an in-memory row store honoring DELETE-then-INSERT semantics.
# ---------------------------------------------------------------------------
# Each row is a dict with keys: title, file_path, chunk_index, content, embedding.

_DELETE_RE = re.compile(
    r"^\s*DELETE\s+FROM\s+(\S+)\s+WHERE\s+file_path\s*=\s*%s\s*$",
    re.IGNORECASE,
)
_INSERT_RE = re.compile(
    r"^\s*INSERT\s+INTO\s+(\S+)\s*\(\s*title\s*,\s*file_path\s*,\s*chunk_index\s*,"
    r"\s*content\s*,\s*embedding\s*\)\s*VALUES",
    re.IGNORECASE,
)


class _FakeCursor:
    def __init__(self, store: list[dict]):
        self._store = store

    def execute(self, sql: str, params=None):
        params = params or ()
        del_match = _DELETE_RE.match(sql)
        if del_match:
            (file_path,) = params
            # Remove every row matching the bound file_path (in place).
            self._store[:] = [
                row for row in self._store if row["file_path"] != file_path
            ]
            return

        if _INSERT_RE.match(sql):
            title, file_path, chunk_index, content, embedding = params
            self._store.append(
                {
                    "title": title,
                    "file_path": file_path,
                    "chunk_index": chunk_index,
                    "content": content,
                    "embedding": embedding,
                }
            )
            return

        raise AssertionError(f"Unexpected SQL issued by ingest_file: {sql!r}")

    def close(self):  # noqa: D401 - trivial
        pass


class _FakeConn:
    """Fake psycopg2-like connection backed by an in-memory row list."""

    def __init__(self):
        self.rows: list[dict] = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return _FakeCursor(self.rows)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


# ---------------------------------------------------------------------------
# Provider stub: deterministic embedding + configured table name.
# ---------------------------------------------------------------------------
class _ProviderStub:
    """Minimal stand-in exposing the surface ``ingest_file`` touches."""

    table_name = "md_embeddings"

    def _embed_query(self, client, chunk: str) -> list:
        # Deterministic, content-derived vector; length is irrelevant to the
        # row-identity property under test. Kept tiny for speed.
        h = float(len(chunk))
        return [h, h + 1.0, h + 2.0]


# ---------------------------------------------------------------------------
# Strategies: generate a set of Markdown documents on disk.
# ---------------------------------------------------------------------------
_stem = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1,
    max_size=12,
).filter(lambda s: s.strip("-_") != "")

# Document bodies: include empty and multi-chunk-sized content so the row set
# spans the "no chunks", "single chunk", and "many chunks" cases.
_body = st.text(max_size=2500)

# A doc set: unique stems mapped to bodies (dict keeps stems unique).
_doc_set = st.dictionaries(keys=_stem, values=_body, min_size=1, max_size=6)


def _materialize(docs_dir: Path, doc_set: dict[str, str]) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    for stem, body in doc_set.items():
        (docs_dir / f"{stem}.md").write_text(body, encoding="utf-8")


def _run_ingestion(conn, provider, docs_dir: Path, pdf_dir: Path) -> None:
    """Ingest every discovered doc once through the fake connection."""
    for doc in discover_documents(docs_dir, pdf_dir):
        ingest_file(conn, provider, embed_client=None, doc=doc)


def _row_key_multiset(rows: list[dict]) -> list[tuple]:
    """Full-row identity used for equality comparison across runs."""
    return sorted(
        (r["title"], r["file_path"], r["chunk_index"], r["content"])
        for r in rows
    )


def _pk_pairs(rows: list[dict]) -> list[tuple]:
    return [(r["file_path"], r["chunk_index"]) for r in rows]


# ===========================================================================
# Property 4: ingestion is idempotent over re-runs (no duplicate rows).
# ===========================================================================
@settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(doc_set=_doc_set)
def test_ingestion_idempotent_over_reruns(tmp_path_factory, doc_set):
    """Feature: pgvector-doc-embeddings, Property 4: Ingestion is idempotent
    over re-runs (no duplicate rows).

    Two identical runs == one run; never a duplicate (file_path, chunk_index).

    Validates: Requirements 5.1
    """
    root = tmp_path_factory.mktemp("idem")
    docs_dir = root / "docs"
    pdf_dir = docs_dir / "to_publish"
    _materialize(docs_dir, doc_set)

    provider = _ProviderStub()

    # --- Single run baseline ---
    single_conn = _FakeConn()
    _run_ingestion(single_conn, provider, docs_dir, pdf_dir)
    single_rows = _row_key_multiset(single_conn.rows)

    # No duplicate (file_path, chunk_index) after a single run.
    single_pks = _pk_pairs(single_conn.rows)
    assert len(single_pks) == len(set(single_pks)), (
        "COUNTEREXAMPLE: duplicate (file_path, chunk_index) after single run: "
        f"{sorted(single_pks)}"
    )

    # --- Two runs over the same unchanged set ---
    double_conn = _FakeConn()
    _run_ingestion(double_conn, provider, docs_dir, pdf_dir)
    _run_ingestion(double_conn, provider, docs_dir, pdf_dir)
    double_rows = _row_key_multiset(double_conn.rows)

    # No duplicate (file_path, chunk_index) after the second run.
    double_pks = _pk_pairs(double_conn.rows)
    assert len(double_pks) == len(set(double_pks)), (
        "COUNTEREXAMPLE: duplicate (file_path, chunk_index) after re-run: "
        f"{sorted(double_pks)}"
    )

    # The two-run result equals the single-run result exactly.
    assert double_rows == single_rows, (
        "COUNTEREXAMPLE: re-running ingestion changed the row set.\n"
        f"  only after single run: {set(map(tuple, single_rows)) - set(map(tuple, double_rows))}\n"
        f"  only after double run: {set(map(tuple, double_rows)) - set(map(tuple, single_rows))}"
    )

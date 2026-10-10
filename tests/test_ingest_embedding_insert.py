"""Per-chunk embedding, insert-mapping, and model/dimension unit tests.

Feature: pgvector-doc-embeddings
Covers optional test task:
- 6.2  Per-chunk embedding, insert-mapping, and model/dimension unit tests

Design: Testing Strategy -> Example / edge-case unit tests:
- "Per-chunk embedding (Req 4.5): with a mocked embed client, assert one
   embedding request per produced chunk."
- "Insert mapping (Req 4.6): with a fake cursor, assert inserted tuples carry
   (title, file_path, chunk_index, content, embedding)."
- "Model/dimension (Req 6.4): assert the script embeds via the provider path
   using EMBEDDING_MODEL and that a wrong-length vector raises."

These are example/edge-case unit tests (not property-based). They exercise
`scripts.ingest_embeddings.ingest_file` against a fake conn/cursor that records
executed SQL and params, plus a provider stub whose `_embed_query` mirrors the
real `OpcpCompanionProvider._embed_query` signature. The wrong-length-vector
case goes through the *real* provider path (`_embed_query`) with a mocked
OpenAI-style embed client to prove the dimension guard raises.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from scripts.ingest_embeddings import DocFile, chunk_text, ingest_file


# ---------------------------------------------------------------------------
# Fakes matching the real conn/cursor/provider signatures used by ingest_file.
# ---------------------------------------------------------------------------

class _RecordingCursor:
    """A DB cursor double that records every (sql, params) it executes."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        self._conn.executed.append((sql, params))
        return None

    def close(self):
        self._conn.cursor_closed = True
        return None


class _RecordingConn:
    """A connection double recording executed SQL, commits, and rollbacks."""

    def __init__(self):
        self.executed = []  # list of (sql, params)
        self.commits = 0
        self.rollbacks = 0
        self.cursor_closed = False

    def cursor(self):
        return _RecordingCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        return None


class _ProviderStub:
    """Provider stub mirroring the attributes/methods ingest_file relies on.

    `_embed_query(client, chunk)` matches the real
    `OpcpCompanionProvider._embed_query` signature and returns a fixed-length
    vector so we can assert the per-chunk request count and insert mapping
    without hitting OVH.
    """

    def __init__(self, table_name="md_embeddings", embedding_dim=4096):
        self.table_name = table_name
        self.embedding_dim = embedding_dim
        self.embed_calls = []  # records (client, chunk) per call

    def _embed_query(self, client, chunk):
        self.embed_calls.append((client, chunk))
        return [0.0] * self.embedding_dim


def _write_md(path: Path, text: str) -> DocFile:
    path.write_text(text, encoding="utf-8")
    return DocFile(path=path, title=path.stem, kind="md")


# ===========================================================================
# Req 4.5 — one embedding request per produced chunk
# ===========================================================================

class TestPerChunkEmbedding:
    def test_one_embedding_request_per_produced_chunk(self, tmp_path):
        """ingest_file issues exactly one embed call per produced chunk.

        Validates: Requirements 4.5
        """
        # Build text long enough to force multiple chunks (default chunk_size=1000).
        text = "x" * 2500
        doc = _write_md(tmp_path / "doc.md", text)

        expected_chunks = chunk_text(text)
        assert len(expected_chunks) > 1, "fixture should produce multiple chunks"

        conn = _RecordingConn()
        provider = _ProviderStub()
        embed_client = object()

        count = ingest_file(conn, provider, embed_client, doc)

        assert count == len(expected_chunks)
        assert len(provider.embed_calls) == len(expected_chunks), (
            "expected exactly one embedding request per produced chunk"
        )
        # Every embed call used the provided embed_client and the chunk content.
        for (client, chunk), expected in zip(provider.embed_calls, expected_chunks):
            assert client is embed_client
            assert chunk == expected

    def test_no_embedding_requests_for_empty_document(self, tmp_path):
        """An empty document yields zero chunks and zero embedding requests.

        Validates: Requirements 4.5
        """
        doc = _write_md(tmp_path / "empty.md", "")

        conn = _RecordingConn()
        provider = _ProviderStub()

        count = ingest_file(conn, provider, object(), doc)

        assert count == 0
        assert provider.embed_calls == []


# ===========================================================================
# Req 4.6 — inserted tuples carry (title, file_path, chunk_index, content, embedding)
# ===========================================================================

class TestInsertMapping:
    def test_inserted_tuples_carry_expected_columns(self, tmp_path):
        """Each INSERT carries (title, file_path, chunk_index, content, embedding).

        Validates: Requirements 4.6
        """
        text = "hello world " * 40  # small -> a single chunk
        doc = _write_md(tmp_path / "note.md", text)
        expected_chunks = chunk_text(text)

        conn = _RecordingConn()
        provider = _ProviderStub()
        embed_client = object()

        ingest_file(conn, provider, embed_client, doc)

        file_path = str(doc.path)

        # First statement must delete the file's existing rows (idempotent upsert).
        delete_sql, delete_params = conn.executed[0]
        assert "delete from" in delete_sql.lower()
        assert provider.table_name in delete_sql
        assert delete_params == (file_path,)

        # Remaining statements are the per-chunk inserts.
        insert_statements = conn.executed[1:]
        assert len(insert_statements) == len(expected_chunks)

        for chunk_index, ((sql, params), chunk) in enumerate(
            zip(insert_statements, expected_chunks)
        ):
            lowered = sql.lower()
            assert "insert into" in lowered
            assert provider.table_name in sql
            # Column list, in order, present in the SQL.
            assert "(title, file_path, chunk_index, content, embedding)" in lowered
            # Embedding is cast to pgvector.
            assert "%s::vector" in lowered

            title, fp, idx, content, embedding = params
            assert title == doc.title
            assert fp == file_path
            assert idx == chunk_index
            assert content == chunk
            # Embedding serialized as the pgvector "[v1,v2,...]" string form.
            assert isinstance(embedding, str)
            assert embedding.startswith("[") and embedding.endswith("]")

    def test_upsert_commits_once_and_closes_cursor(self, tmp_path):
        """ingest_file commits the per-file transaction and closes the cursor.

        Validates: Requirements 4.6
        """
        doc = _write_md(tmp_path / "commit.md", "some content")

        conn = _RecordingConn()
        provider = _ProviderStub()

        ingest_file(conn, provider, object(), doc)

        assert conn.commits == 1
        assert conn.rollbacks == 0
        assert conn.cursor_closed is True


# ===========================================================================
# Req 6.4 — provider path uses EMBEDDING_MODEL; wrong-length vector raises
# ===========================================================================

class TestModelAndDimension:
    def test_embedding_goes_through_provider_path_using_embedding_model(self):
        """The real provider `_embed_query` calls the client with EMBEDDING_MODEL.

        Validates: Requirements 6.4
        """
        from app.oracle.ai_providers import OpcpCompanionProvider

        provider = OpcpCompanionProvider()

        embed_client = MagicMock()
        embed_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.0] * provider.embedding_dim)]
        )

        vector = provider._embed_query(embed_client, "some chunk text")

        assert len(vector) == provider.embedding_dim
        # The request went through the provider path using EMBEDDING_MODEL.
        embed_client.embeddings.create.assert_called_once()
        _, kwargs = embed_client.embeddings.create.call_args
        assert kwargs["model"] == provider.embedding_model
        assert kwargs["model"] == "Qwen3-Embedding-8B"
        assert kwargs["input"] == ["some chunk text"]

    def test_wrong_length_vector_raises_via_provider_path(self):
        """A wrong-length embedding vector raises through the provider path.

        Validates: Requirements 6.4
        """
        from app.oracle.ai_providers import OpcpCompanionProvider

        provider = OpcpCompanionProvider()

        # Client returns a vector of the wrong dimension.
        wrong_len = provider.embedding_dim - 1
        embed_client = MagicMock()
        embed_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.0] * wrong_len)]
        )

        with pytest.raises(Exception) as exc:
            provider._embed_query(embed_client, "chunk")

        # The message reports the unexpected dimension.
        assert str(wrong_len) in str(exc.value)
        assert str(provider.embedding_dim) in str(exc.value)

    def test_ingest_file_propagates_wrong_length_vector_and_rolls_back(self, tmp_path):
        """A wrong-length vector during ingest surfaces and triggers rollback.

        Uses the real provider `_embed_query` (via a mocked embed client) so the
        dimension guard executes on the actual provider path, wired through
        ingest_file's per-file transaction.

        Validates: Requirements 6.4
        """
        from app.oracle.ai_providers import OpcpCompanionProvider

        provider = OpcpCompanionProvider()

        embed_client = MagicMock()
        embed_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.0] * (provider.embedding_dim - 1))]
        )

        doc = _write_md(tmp_path / "bad.md", "content that will be embedded")
        conn = _RecordingConn()

        with pytest.raises(Exception):
            ingest_file(conn, provider, embed_client, doc)

        # The failing transaction was rolled back and never committed.
        assert conn.rollbacks == 1
        assert conn.commits == 0
        assert conn.cursor_closed is True

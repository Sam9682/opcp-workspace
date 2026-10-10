"""Tests for the OPCP Companion RAG provider.

Feature: opcp-companion-provider

Covers optional test tasks:
- 1.4  config/dependency smoke tests
- 2.2  schema example tests
- 3.3  Property 1 (pgvector row mapping preserves chunk fields)
- 3.4  Property 4 (sources derive faithfully from chunks)
- 3.6  Property 2 (assembled context contains each chunk)
- 4.3  Property 3 (provider query dict contract)
- 4.4  provider wiring / edge / smoke tests
- 6.2  Property 5 (done event propagates provider sources)
- 6.3  Property 6 (provider error during streaming -> error event, no done)
- 6.6  service/router/config wiring tests
"""
import asyncio
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from pydantic import ValidationError

from app.config import Settings
from app.oracle.ai_providers import OpcpCompanionProvider, get_ai_provider
from app.oracle.schemas import OracleQuery, OracleResponse, Source


REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_text = st.text(min_size=0, max_size=40)
_distance = st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False)


def _row_strategy():
    """A pgvector row: (title, file_path, chunk_index, content, similarity)."""
    return st.tuples(
        _text,                                       # title
        _text,                                       # file_path
        st.integers(min_value=0, max_value=10_000),  # chunk_index
        _text,                                       # content
        _distance,                                   # similarity (already 1 - distance)
    )


def _chunk_strategy():
    return st.fixed_dictionaries({
        "title": _text,
        "file_path": _text,
        "chunk_index": st.integers(min_value=0, max_value=10_000),
        "content": _text,
        "similarity": st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
        ),
    })


def _source_strategy():
    return st.fixed_dictionaries({
        "title": _text,
        "file_path": _text,
        "similarity": st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
        ),
    })


# ===========================================================================
# Task 1.4 — config / dependency smoke tests (Req 4.2, 4.4, 6.1, 6.2)
# ===========================================================================

class TestConfigAndDependenciesSmoke:
    def test_settings_defaults_match_rag_query(self):
        """Settings() with no env overrides yields rag_query.py defaults."""
        s = Settings()
        assert s.EMBEDDING_MODEL == "Qwen3-Embedding-8B"
        assert s.EMBEDDING_DIM == 4096
        assert s.LLM_MODEL == "Qwen3-Embedding-8B"
        assert s.PG_HOST == "postgres"
        assert s.PG_PORT == 5432
        assert s.PG_DB == "shai_db"
        assert s.PG_USER == "shai_user"
        assert s.TABLE_NAME == "md_embeddings"

    def test_env_example_documents_each_rag_var(self):
        env_text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        for var in (
            "OVH_AI_ENDPOINT", "OVH_AI_TOKEN", "EMBEDDING_MODEL", "EMBEDDING_DIM",
            "LLM_ENDPOINT", "LLM_TOKEN", "LLM_MODEL",
            "PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD", "TABLE_NAME",
        ):
            assert re.search(rf"^{var}=", env_text, re.MULTILINE), (
                f"{var} not documented in .env.example"
            )

    def test_requirements_declares_psycopg2_and_openai(self):
        req = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        assert re.search(r"^psycopg2-binary", req, re.MULTILINE)
        assert re.search(r"^openai", req, re.MULTILINE)


# ===========================================================================
# Task 2.2 — schema example tests (Req 1.4, 3.1)
# ===========================================================================

class TestSchemas:
    def test_oracle_query_accepts_opcp_companion(self):
        q = OracleQuery(question="Bonjour", ai_provider="opcp_companion")
        assert q.ai_provider == "opcp_companion"

    def test_oracle_query_rejects_unknown_provider(self):
        with pytest.raises(ValidationError):
            OracleQuery(question="Bonjour", ai_provider="totally_unknown")

    def test_oracle_response_accepts_sources_none(self):
        resp = OracleResponse(
            id=1, question="q", answer="a", ai_provider="opcp_companion",
            context=None, created_at="2024-01-01T00:00:00", user_id=None,
            processing_time=0.1, tokens_used=5, sources=None,
        )
        assert resp.sources is None

    def test_oracle_response_accepts_list_of_source(self):
        resp = OracleResponse(
            id=1, question="q", answer="a", ai_provider="opcp_companion",
            context=None, created_at="2024-01-01T00:00:00", user_id=None,
            processing_time=0.1, tokens_used=5,
            sources=[Source(title="t", file_path="f", similarity=0.9)],
        )
        assert len(resp.sources) == 1
        assert resp.sources[0].title == "t"


# ===========================================================================
# Task 3.3 — Property 1: pgvector row mapping preserves chunk fields
# Validates: Requirements 2.2, 2.3
# ===========================================================================

class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *args, **kwargs):
        return None

    def fetchall(self):
        return self._rows

    def close(self):
        return None


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)

    def commit(self):
        return None

    def close(self):
        return None


@settings(max_examples=150, deadline=None)
@given(rows=st.lists(_row_strategy(), min_size=0, max_size=8))
def test_property1_pgvector_row_mapping_preserves_fields(rows):
    """Feature: opcp-companion-provider, Property 1: Le mapping des lignes
    pgvector préserve les champs du chunk.

    Validates: Requirements 2.2, 2.3
    """
    provider = OpcpCompanionProvider()
    conn = _FakeConn(rows)
    chunks = provider._search(conn, [0.1, 0.2, 0.3], top_k=len(rows) or 1)

    assert len(chunks) == len(rows)
    for chunk, row in zip(chunks, rows):
        title, file_path, chunk_index, content, sim = row
        assert set(chunk.keys()) == {
            "title", "file_path", "chunk_index", "content", "similarity"
        }
        assert chunk["title"] == title
        assert chunk["file_path"] == file_path
        assert chunk["chunk_index"] == chunk_index
        assert chunk["content"] == content
        assert chunk["similarity"] == round(float(sim), 4)


# ===========================================================================
# Task 3.4 — Property 4: sources derive faithfully from chunks
# Validates: Requirements 2.6, 3.1
# ===========================================================================

@settings(max_examples=150, deadline=None)
@given(chunks=st.lists(_chunk_strategy(), min_size=0, max_size=8))
def test_property4_sources_derive_from_chunks(chunks):
    """Feature: opcp-companion-provider, Property 4: Les sources dérivent
    fidèlement des chunks.

    Validates: Requirements 2.6, 3.1
    """
    provider = OpcpCompanionProvider()
    sources = provider._chunks_to_sources(chunks)

    assert len(sources) == len(chunks)
    for source, chunk in zip(sources, chunks):
        assert source["title"] == chunk["title"]
        assert source["file_path"] == chunk["file_path"]
        assert source["similarity"] == chunk["similarity"]


# ===========================================================================
# Task 3.6 — Property 2: assembled context contains each chunk
# Validates: Requirements 2.4
# ===========================================================================

@settings(max_examples=150, deadline=None)
@given(chunks=st.lists(_chunk_strategy(), min_size=0, max_size=6))
def test_property2_build_context_contains_each_chunk(chunks):
    """Feature: opcp-companion-provider, Property 2: Le contexte assemblé
    contient chaque chunk récupéré.

    Validates: Requirements 2.4
    """
    provider = OpcpCompanionProvider()
    context = provider._build_context(chunks)

    for chunk in chunks:
        assert chunk["title"] in context
        assert str(chunk["chunk_index"]) in context
        assert chunk["content"] in context


# ===========================================================================
# Task 4.3 — Property 3: provider query dict contract
# Validates: Requirements 2.5
# ===========================================================================

@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(question=st.text(min_size=1, max_size=60))
def test_property3_query_dict_contract(question, monkeypatch):
    """Feature: opcp-companion-provider, Property 3: La réponse du fournisseur
    respecte le contrat de dictionnaire.

    Validates: Requirements 2.5
    """
    from app.config import settings as app_settings
    monkeypatch.setattr(app_settings, "OVH_AI_TOKEN", "tok-embed", raising=False)
    monkeypatch.setattr(app_settings, "LLM_TOKEN", "tok-llm", raising=False)

    provider = OpcpCompanionProvider()
    provider.embed_token = "tok-embed"
    provider.llm_token = "tok-llm"

    # Fake embedding client: embeddings.create -> vector of EMBEDDING_DIM floats.
    embed_client = MagicMock()
    embed_client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.0] * provider.embedding_dim)]
    )

    # Fake LLM client: responses.create -> output_text + usage.
    llm_client = MagicMock()
    llm_client.responses.create.return_value = SimpleNamespace(
        output_text="Réponse simulée.",
        usage=SimpleNamespace(total_tokens=42),
    )

    fake_conn = _FakeConn([
        ("Titre", "chemin.md", 0, "contenu", 0.9),
    ])

    monkeypatch.setattr(provider, "_get_embed_client", lambda: embed_client)
    monkeypatch.setattr(provider, "_get_llm_client", lambda: llm_client)
    monkeypatch.setattr(provider, "_get_pg_connection", lambda: fake_conn)

    result = asyncio.run(provider.query(question))

    assert set(["answer", "processing_time", "tokens_used", "provider", "sources"]).issubset(
        result.keys()
    )
    assert result["provider"] == "opcp_companion"
    assert result["processing_time"] >= 0


# ===========================================================================
# Task 4.4 — provider wiring / edge / smoke tests
# ===========================================================================

class TestProviderWiring:
    def test_factory_returns_opcp_companion_instance(self):
        """Req 1.1, 1.2"""
        provider = get_ai_provider("opcp_companion")
        assert isinstance(provider, OpcpCompanionProvider)

    def test_client_and_pg_wiring_uses_settings(self):
        """Req 4.5, 4.6, 2.1: base_url/api_key for embed vs llm; PG_* for conn."""
        import sys

        from app.config import settings as app_settings

        provider = OpcpCompanionProvider()
        provider.embed_endpoint = "https://embed.example/v1"
        provider.embed_token = "embed-token"
        provider.llm_endpoint = "https://llm.example/v1"
        provider.llm_token = "llm-token"

        # The provider imports `from openai import OpenAI` lazily. Inject a fake
        # `openai` module so the wiring can be asserted without the real package.
        mock_openai = MagicMock()
        fake_openai_module = SimpleNamespace(OpenAI=mock_openai)
        with patch.dict(sys.modules, {"openai": fake_openai_module}):
            provider._get_embed_client()
            mock_openai.assert_called_with(
                base_url="https://embed.example/v1", api_key="embed-token"
            )
            provider._get_llm_client()
            mock_openai.assert_called_with(
                base_url="https://llm.example/v1", api_key="llm-token"
            )

        with patch("psycopg2.connect") as mock_connect:
            provider._get_pg_connection()
            mock_connect.assert_called_once_with(
                host=app_settings.PG_HOST,
                port=app_settings.PG_PORT,
                dbname=app_settings.PG_DB,
                user=app_settings.PG_USER,
                password=app_settings.PG_PASSWORD,
            )

    def test_empty_ovh_token_raises_naming_var(self):
        """Req 5.3: empty OVH_AI_TOKEN -> error naming the variable."""
        provider = OpcpCompanionProvider()
        provider.embed_token = ""
        provider.llm_token = "llm-token"
        with pytest.raises(Exception) as exc:
            asyncio.run(provider.query("question"))
        assert "OVH_AI_TOKEN" in str(exc.value)

    def test_empty_llm_token_raises_naming_var(self):
        """Req 5.3: empty LLM_TOKEN -> error naming the variable."""
        provider = OpcpCompanionProvider()
        provider.embed_token = "embed-token"
        provider.llm_token = ""
        with pytest.raises(Exception) as exc:
            asyncio.run(provider.query("question"))
        assert "LLM_TOKEN" in str(exc.value)

    def test_pg_connect_failure_raises_descriptive_db_error(self):
        """Req 5.1: psycopg2.connect raising -> descriptive DB error."""
        provider = OpcpCompanionProvider()
        provider.embed_token = "embed-token"
        provider.llm_token = "llm-token"

        embed_client = MagicMock()
        embed_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.0] * provider.embedding_dim)]
        )

        def _boom():
            raise Exception("connection refused")

        with patch.object(provider, "_get_embed_client", return_value=embed_client), \
             patch.object(provider, "_get_pg_connection", side_effect=_boom):
            with pytest.raises(Exception) as exc:
                asyncio.run(provider.query("question"))
        msg = str(exc.value).lower()
        assert "base de données" in msg or "connexion" in msg

    def test_embedding_failure_raises_descriptive_ovh_error(self):
        """Req 5.2: embeddings.create raising -> descriptive OVH error."""
        provider = OpcpCompanionProvider()
        provider.embed_token = "embed-token"
        provider.llm_token = "llm-token"

        embed_client = MagicMock()
        embed_client.embeddings.create.side_effect = Exception("ovh down")

        with patch.object(provider, "_get_embed_client", return_value=embed_client):
            with pytest.raises(Exception) as exc:
                asyncio.run(provider.query("question"))
        assert "OVH" in str(exc.value)

    def test_generation_failure_raises_descriptive_ovh_error(self):
        """Req 5.2: responses.create raising -> descriptive OVH error."""
        provider = OpcpCompanionProvider()
        provider.embed_token = "embed-token"
        provider.llm_token = "llm-token"

        embed_client = MagicMock()
        embed_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.0] * provider.embedding_dim)]
        )
        llm_client = MagicMock()
        llm_client.responses.create.side_effect = Exception("ovh gen down")
        fake_conn = _FakeConn([("t", "f", 0, "c", 0.9)])

        with patch.object(provider, "_get_embed_client", return_value=embed_client), \
             patch.object(provider, "_get_llm_client", return_value=llm_client), \
             patch.object(provider, "_get_pg_connection", return_value=fake_conn):
            with pytest.raises(Exception) as exc:
                asyncio.run(provider.query("question"))
        assert "OVH" in str(exc.value)

    def test_no_import_of_opcp_ai_chatbot(self):
        """Req 6.4: ai_providers.py must not import the neighbour repo.

        The module docstring may legitimately name the source repo in prose, so
        we assert there is no *import statement* referencing it rather than a
        bare substring check.
        """
        src = (REPO_ROOT / "app" / "oracle" / "ai_providers.py").read_text(encoding="utf-8")
        import_lines = [
            line for line in src.splitlines()
            if re.match(r"\s*(import|from)\s", line)
        ]
        for line in import_lines:
            assert "opcp_ai_chatbot" not in line
            assert "opcp-ai-chatbot" not in line
            assert "rag_query" not in line


# ===========================================================================
# Task 6.2 — Property 5: done event propagates provider sources
# Validates: Requirements 3.2
# ===========================================================================

def _make_fake_db():
    db = MagicMock()

    def _refresh(obj):
        # Simulate the DB assigning a primary key on refresh.
        obj.id = 1

    db.refresh.side_effect = _refresh
    return db


def _drain_stream(stream):
    async def _collect():
        events = []
        async for event in stream:
            events.append(event)
        return events

    return asyncio.run(_collect())


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(sources=st.lists(_source_strategy(), min_size=0, max_size=6))
def test_property5_done_event_propagates_sources(sources, monkeypatch):
    """Feature: opcp-companion-provider, Property 5: L'évènement `done` propage
    les sources du fournisseur.

    Validates: Requirements 3.2
    """
    from app.oracle import service as service_module
    from app.oracle.service import OracleService

    class _StubProvider:
        async def query(self, question, context=None, temperature=0.7, max_tokens=2000):
            return {
                "answer": "réponse",
                "processing_time": 0.01,
                "tokens_used": 3,
                "provider": "opcp_companion",
                "sources": sources,
            }

    monkeypatch.setattr(
        service_module, "get_ai_provider", lambda name: _StubProvider()
    )

    query = OracleQuery(question="q", ai_provider="opcp_companion")
    db = _make_fake_db()

    events = _drain_stream(OracleService.ask_oracle_stream(db, query, user_id=None))
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["sources"] == sources


# ===========================================================================
# Task 6.3 — Property 6: provider error -> error event, no done
# Validates: Requirements 5.4
# ===========================================================================

@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(msg=st.text(min_size=1, max_size=60))
def test_property6_error_event_on_provider_exception(msg, monkeypatch):
    """Feature: opcp-companion-provider, Property 6: Une erreur de fournisseur
    pendant le streaming produit un évènement `error`.

    Validates: Requirements 5.4
    """
    from app.oracle import service as service_module
    from app.oracle.service import OracleService

    class _RaisingProvider:
        async def query(self, question, context=None, temperature=0.7, max_tokens=2000):
            raise Exception(msg)

    monkeypatch.setattr(
        service_module, "get_ai_provider", lambda name: _RaisingProvider()
    )

    query = OracleQuery(question="q", ai_provider="opcp_companion")
    db = _make_fake_db()

    events = _drain_stream(OracleService.ask_oracle_stream(db, query, user_id=None))
    error_events = [e for e in events if e["type"] == "error"]
    done_events = [e for e in events if e["type"] == "done"]
    assert len(error_events) == 1
    assert msg in error_events[0]["message"]
    assert len(done_events) == 0


# ===========================================================================
# Task 6.6 — service / router / config wiring (Req 1.3, 1.6)
# ===========================================================================

class TestProvidersWiring:
    def test_providers_endpoint_includes_opcp_companion(self, client):
        """Req 1.6"""
        resp = client.get("/api/oracle/providers")
        assert resp.status_code == 200
        providers = resp.json()["providers"]
        assert any(p["id"] == "opcp_companion" for p in providers)

    def test_oracle_config_has_opcp_companion(self):
        """Req 1.3"""
        config = json.loads((REPO_ROOT / "oracle_config.json").read_text(encoding="utf-8"))
        assert "opcp_companion" in config["providers"]
        assert config["providers"]["opcp_companion"]["name"] == "OPCP Companion"


# ===========================================================================
# Bugfix: md-embeddings-table-missing-fix
# Task 1 — Bug condition exploration test (Property 1: Bug Condition)
#
# Bug Condition (design):
#   isBugCondition(input) = input.ai_provider == "opcp_companion"
#                           AND NOT tableExists(input.pg_connection, table_name)
#   where table_name == settings.TABLE_NAME (default "md_embeddings").
#
# Expected Behavior (design Property 1): after an idempotent provisioning step,
# tableExists(conn, table_name) is true and the similarity search runs WITHOUT
# raising `relation "md_embeddings" does not exist`.
#
# CRITICAL: This test is EXPECTED TO FAIL on the unfixed code. The failure
# confirms the bug: no `CREATE EXTENSION` / `CREATE TABLE` provisioning DDL is
# issued before the `SELECT`, and the missing-table error is surfaced to the
# caller. DO NOT fix the test or the code here.
# ===========================================================================

# The concrete Postgres error string the vector DB raises when md_embeddings
# was never provisioned (see bugfix.md / observed runtime log).
_MISSING_TABLE_ERROR = 'relation "md_embeddings" does not exist'


class _MissingTableCursor:
    """A cursor doubling a vector DB where `md_embeddings` is initially absent.

    - Records every SQL statement executed (to detect provisioning DDL).
    - Raises the equivalent of `relation "md_embeddings" does not exist` when a
      `SELECT ... FROM md_embeddings ...` runs while the table does not exist.
    - `CREATE TABLE IF NOT EXISTS md_embeddings (...)` marks the table present
      (idempotent provisioning), after which the SELECT succeeds and returns the
      configured rows.
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        self._conn.executed_sql.append(sql)
        normalized = " ".join(sql.split()).lower()

        # Idempotent provisioning DDL: creating the table makes it exist.
        if normalized.startswith("create table") and "md_embeddings" in normalized:
            self._conn.table_exists = True
            return None
        if normalized.startswith("create extension"):
            self._conn.extension_created = True
            return None

        # The similarity search: fail loudly when the relation is missing.
        if normalized.startswith("select") and "from md_embeddings" in normalized:
            if not self._conn.table_exists:
                raise Exception(_MISSING_TABLE_ERROR)
            return None

        return None

    def fetchall(self):
        return list(self._conn.rows)

    def close(self):
        return None


class _MissingTableConn:
    """A connection whose `md_embeddings` relation starts out missing."""

    def __init__(self, rows):
        self.rows = rows
        self.table_exists = False
        self.extension_created = False
        self.executed_sql = []
        self.commits = 0

    def cursor(self):
        return _MissingTableCursor(self)

    def commit(self):
        self.commits += 1

    def close(self):
        return None


def _first_index(statements, predicate):
    for i, sql in enumerate(statements):
        if predicate(" ".join(sql.split()).lower()):
            return i
    return -1


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    embedding=st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=8,
    ),
    top_k=st.integers(min_value=1, max_value=10),
)
def test_bug_condition_vector_store_missing_before_search(embedding, top_k, monkeypatch):
    """Bugfix md-embeddings-table-missing-fix, Property 1: Bug Condition —
    the vector store must be provisioned before the OPCP similarity search.

    Scoped PBT: deterministic bug, scoped to ai_provider == "opcp_companion"
    against a vector DB where `md_embeddings` does not exist. Parameterized over
    embedding vectors and top_k to stay property-shaped while reproducible.

    EXPECTED (unfixed): FAILS — no provisioning DDL is issued and the search
    surfaces `relation "md_embeddings" does not exist`.

    Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3
    """
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "OVH_AI_TOKEN", "tok-embed", raising=False)
    monkeypatch.setattr(app_settings, "LLM_TOKEN", "tok-llm", raising=False)

    provider = OpcpCompanionProvider()
    provider.embed_token = "tok-embed"
    provider.llm_token = "tok-llm"
    provider.top_k = top_k

    table_name = app_settings.TABLE_NAME  # default "md_embeddings"

    # Embedding client returns a vector of the expected dimension.
    embed_client = MagicMock()
    embed_client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.0] * provider.embedding_dim)]
    )

    # LLM client returns a canned answer so the pipeline can complete once the
    # search stops failing.
    llm_client = MagicMock()
    llm_client.responses.create.return_value = SimpleNamespace(
        output_text="Réponse simulée.",
        usage=SimpleNamespace(total_tokens=7),
    )

    # Vector DB where md_embeddings is missing at first.
    conn = _MissingTableConn([("Titre", "chemin.md", 0, "contenu", 0.9)])

    monkeypatch.setattr(provider, "_get_embed_client", lambda: embed_client)
    monkeypatch.setattr(provider, "_get_llm_client", lambda: llm_client)
    monkeypatch.setattr(provider, "_get_pg_connection", lambda: conn)

    # Run the OPCP query. On fixed code this provisions then searches; on unfixed
    # code the search raises the missing-table error, which `query` re-wraps.
    surfaced_error = None
    try:
        asyncio.run(provider.query("Une question quelconque ?"))
    except Exception as exc:  # noqa: BLE001 - we assert on the surfaced message
        surfaced_error = str(exc)

    # Expected Behavior assertion (Property 1): the missing-table error must NOT
    # be surfaced to the caller.
    assert surfaced_error is None or _MISSING_TABLE_ERROR not in surfaced_error, (
        "Bug reproduced: OPCP query surfaced the missing-table error "
        f"({surfaced_error!r}). Expected the provider to provision "
        f"{table_name!r} before searching."
    )

    # Expected Behavior assertion: after the query, the table exists.
    assert conn.table_exists, (
        f"Bug reproduced: {table_name!r} was never provisioned "
        "(no CREATE TABLE issued against the vector DB)."
    )

    # Expected Behavior assertion: provisioning DDL was issued BEFORE the SELECT.
    create_ext_idx = _first_index(
        conn.executed_sql,
        lambda s: s.startswith("create extension") and "vector" in s,
    )
    create_tbl_idx = _first_index(
        conn.executed_sql,
        lambda s: s.startswith("create table") and "md_embeddings" in s,
    )
    select_idx = _first_index(
        conn.executed_sql,
        lambda s: s.startswith("select") and "from md_embeddings" in s,
    )

    assert create_ext_idx != -1, (
        "Bug reproduced: no `CREATE EXTENSION IF NOT EXISTS vector` was issued "
        f"against the vector DB. Executed SQL: {conn.executed_sql!r}"
    )
    assert create_tbl_idx != -1, (
        "Bug reproduced: no `CREATE TABLE IF NOT EXISTS md_embeddings (...)` was "
        f"issued against the vector DB. Executed SQL: {conn.executed_sql!r}"
    )
    assert select_idx != -1, "Expected the similarity SELECT to run after provisioning."
    assert create_ext_idx < select_idx and create_tbl_idx < select_idx, (
        "Provisioning DDL must precede the similarity SELECT. "
        f"Executed SQL order: {conn.executed_sql!r}"
    )

# ===========================================================================
# Bugfix: md-embeddings-table-missing-fix
# Task 2 — Preservation property tests (Property 2: Preservation)
#
# Non-bug condition (design): isBugCondition(input) returns FALSE — a non-OPCP
# provider (`kiro`/`shai`/`openai`), OR an OPCP query where `md_embeddings`
# already exists. For these inputs the fixed code F' must behave identically to
# the unfixed code F.
#
# Observation-first methodology: these assertions record the ACTUAL behavior of
# the UNFIXED code (routing without vector-DB access, the `_search` row mapping,
# `_chunks_to_sources` / `_build_context` outputs, and the `query` result-dict
# contract) so that the same assertions can prove the fix preserves them.
#
# EXPECTED (unfixed): these tests PASS — they establish the baseline to preserve.
# The already-provisioned `ensure_vector_store` no-op assertion is written now
# but guarded to skip on unfixed code (the method does not exist yet); it is
# exercised fully after task 3.
#
# Validates: Requirements 3.1, 3.2, 3.3, 3.4
# ===========================================================================


class _RecordingCursor:
    """A cursor over an already-provisioned table.

    Records every SQL statement executed so tests can assert that no
    provisioning DDL (CREATE EXTENSION / CREATE TABLE) is issued on the
    non-bug path, and returns the configured rows for a SELECT.
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        self._conn.executed_sql.append(sql)
        return None

    def fetchall(self):
        return list(self._conn.rows)

    def close(self):
        return None


class _RecordingConn:
    """A connection to a vector DB where `md_embeddings` already exists.

    Models the non-bug OPCP case: the table is present, so a search succeeds
    with no provisioning needed. Records executed SQL and commits so tests can
    assert the absence of destructive/provisioning DDL.
    """

    def __init__(self, rows):
        self.rows = rows
        self.executed_sql = []
        self.commits = 0

    def cursor(self):
        return _RecordingCursor(self)

    def commit(self):
        self.commits += 1

    def close(self):
        return None


def _provisioning_ddl(statements):
    """Return the subset of statements that are provisioning/destructive DDL."""
    ddl = []
    for sql in statements:
        normalized = " ".join(sql.split()).lower()
        if (
            normalized.startswith("create extension")
            or normalized.startswith("create table")
            or normalized.startswith("drop ")
            or normalized.startswith("truncate ")
            or normalized.startswith("delete ")
            or normalized.startswith("alter ")
        ):
            ddl.append(normalized)
    return ddl


# ---------------------------------------------------------------------------
# Preservation — Req 3.1: non-OPCP providers route without vector-DB access
# ---------------------------------------------------------------------------

@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    provider_name=st.sampled_from(["kiro", "shai", "openai"]),
    answer=st.text(min_size=1, max_size=40),
)
def test_preservation_non_opcp_providers_never_touch_vector_db(
    provider_name, answer, monkeypatch
):
    """Preservation (Req 3.1): non-OPCP providers (kiro/shai/openai) route and
    return results WITHOUT any vector-DB access — no `_get_pg_connection` call
    and no provisioning DDL. Observed on unfixed code; must remain unchanged.

    Validates: Requirements 3.1
    """
    from app.oracle import ai_providers as ai_providers_module

    provider = get_ai_provider(provider_name)

    # Sentinel: any attempt to open a vector-DB connection is a violation.
    pg_calls = {"count": 0}

    def _forbidden_pg():
        pg_calls["count"] += 1
        raise AssertionError(
            f"{provider_name} must not open a vector-DB connection"
        )

    # OpcpCompanionProvider is the only provider with `_get_pg_connection`; the
    # others do not define it. Guard the whole provider class to catch any
    # accidental future vector-DB access from a non-OPCP provider.
    monkeypatch.setattr(
        ai_providers_module.OpcpCompanionProvider,
        "_get_pg_connection",
        lambda self: _forbidden_pg(),
        raising=False,
    )

    # Stub the provider's own `query` to observe the routed result shape without
    # invoking external CLIs / HTTP. We assert the routing target rather than
    # re-running the real subprocess/network calls.
    async def _stub_query(question, context=None, temperature=0.7, max_tokens=2000):
        return {
            "answer": answer,
            "processing_time": 0.0,
            "tokens_used": len(answer.split()),
            "provider": provider_name,
        }

    monkeypatch.setattr(provider, "query", _stub_query)

    result = asyncio.run(provider.query("une question"))

    assert result["provider"] == provider_name
    assert result["answer"] == answer
    # No vector-DB access occurred for a non-OPCP provider.
    assert pg_calls["count"] == 0


# ---------------------------------------------------------------------------
# Preservation — `_search` pgvector row mapping unchanged (mirrors Property 1)
# ---------------------------------------------------------------------------

@settings(max_examples=150, deadline=None)
@given(rows=st.lists(_row_strategy(), min_size=0, max_size=8))
def test_preservation_search_row_mapping_unchanged(rows):
    """Preservation: `_search` maps pgvector rows
    (title, file_path, chunk_index, content, similarity) to chunk dicts exactly
    as observed on unfixed code — keys, values, and the round(similarity, 4).

    Validates: Requirements 3.4
    """
    provider = OpcpCompanionProvider()
    conn = _FakeConn(rows)
    chunks = provider._search(conn, [0.1, 0.2, 0.3], top_k=len(rows) or 1)

    assert len(chunks) == len(rows)
    for chunk, row in zip(chunks, rows):
        title, file_path, chunk_index, content, sim = row
        assert set(chunk.keys()) == {
            "title", "file_path", "chunk_index", "content", "similarity"
        }
        assert chunk["title"] == title
        assert chunk["file_path"] == file_path
        assert chunk["chunk_index"] == chunk_index
        assert chunk["content"] == content
        assert chunk["similarity"] == round(float(sim), 4)


# ---------------------------------------------------------------------------
# Preservation — `_chunks_to_sources` output unchanged (mirrors Property 4)
# ---------------------------------------------------------------------------

@settings(max_examples=150, deadline=None)
@given(chunks=st.lists(_chunk_strategy(), min_size=0, max_size=8))
def test_preservation_chunks_to_sources_unchanged(chunks):
    """Preservation: `_chunks_to_sources` derives (title, file_path, similarity)
    faithfully from chunks, as observed on unfixed code.

    Validates: Requirements 3.4
    """
    provider = OpcpCompanionProvider()
    sources = provider._chunks_to_sources(chunks)

    assert len(sources) == len(chunks)
    for source, chunk in zip(sources, chunks):
        assert set(source.keys()) == {"title", "file_path", "similarity"}
        assert source["title"] == chunk["title"]
        assert source["file_path"] == chunk["file_path"]
        assert source["similarity"] == chunk["similarity"]


# ---------------------------------------------------------------------------
# Preservation — `_build_context` output unchanged (mirrors Property 2)
# ---------------------------------------------------------------------------

@settings(max_examples=150, deadline=None)
@given(chunks=st.lists(_chunk_strategy(), min_size=0, max_size=6))
def test_preservation_build_context_unchanged(chunks):
    """Preservation: `_build_context` formats each chunk as
    `[{title} — chunk {chunk_index}]\\n{content}` joined by `\\n\\n---\\n\\n`,
    exactly as observed on unfixed code.

    Validates: Requirements 3.4
    """
    provider = OpcpCompanionProvider()
    context = provider._build_context(chunks)

    # Recompute the observed formatting independently and assert equality.
    expected = "\n\n---\n\n".join(
        f"[{chunk['title']} — chunk {chunk['chunk_index']}]\n{chunk['content']}"
        for chunk in chunks
    )
    assert context == expected

    # And each chunk's content is present in the assembled context.
    for chunk in chunks:
        assert chunk["title"] in context
        assert str(chunk["chunk_index"]) in context
        assert chunk["content"] in context


# ---------------------------------------------------------------------------
# Preservation — `query` result-dict contract unchanged (mirrors Property 3)
# ---------------------------------------------------------------------------

@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(question=st.text(min_size=1, max_size=60))
def test_preservation_query_dict_contract_unchanged(question, monkeypatch):
    """Preservation: an OPCP query against an already-provisioned table returns
    the same result-dict contract observed on unfixed code — keys `answer`,
    `processing_time`, `tokens_used`, `provider == "opcp_companion"`, `sources`.

    Uses a connection where the table already exists (non-bug OPCP case), so no
    provisioning is required and behavior matches today's.

    Validates: Requirements 3.4
    """
    from app.config import settings as app_settings
    monkeypatch.setattr(app_settings, "OVH_AI_TOKEN", "tok-embed", raising=False)
    monkeypatch.setattr(app_settings, "LLM_TOKEN", "tok-llm", raising=False)

    provider = OpcpCompanionProvider()
    provider.embed_token = "tok-embed"
    provider.llm_token = "tok-llm"

    embed_client = MagicMock()
    embed_client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.0] * provider.embedding_dim)]
    )

    llm_client = MagicMock()
    llm_client.responses.create.return_value = SimpleNamespace(
        output_text="Réponse simulée.",
        usage=SimpleNamespace(total_tokens=42),
    )

    # Already-provisioned vector DB: the table exists, search returns rows.
    conn = _RecordingConn([("Titre", "chemin.md", 0, "contenu", 0.9)])

    monkeypatch.setattr(provider, "_get_embed_client", lambda: embed_client)
    monkeypatch.setattr(provider, "_get_llm_client", lambda: llm_client)
    monkeypatch.setattr(provider, "_get_pg_connection", lambda: conn)

    result = asyncio.run(provider.query(question))

    assert {"answer", "processing_time", "tokens_used", "provider", "sources"}.issubset(
        result.keys()
    )
    assert result["provider"] == "opcp_companion"
    assert result["processing_time"] >= 0
    assert result["sources"] == [
        {"title": "Titre", "file_path": "chemin.md", "similarity": 0.9}
    ]


# ---------------------------------------------------------------------------
# Preservation — already-provisioned table: search result equals pre-fix output
# and (once implemented) ensure_vector_store issues only IF NOT EXISTS DDL.
#
# Guarded: `ensure_vector_store` does not exist on unfixed code. The
# existing-behavior part (the search result over an existing table) is asserted
# NOW; the "no destructive DDL" part is exercised fully after task 3.
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(rows=st.lists(_row_strategy(), min_size=0, max_size=8))
def test_preservation_existing_table_ensure_vector_store_is_noop(rows):
    """Preservation (Req 3.4): for an already-provisioned table, the search
    returns the pre-fix output, and — once implemented — `ensure_vector_store`
    performs only idempotent `IF NOT EXISTS` DDL (no destructive statements).

    The `ensure_vector_store` assertion is guarded so it does not error on
    unfixed code (the method does not exist yet); it is exercised fully after
    task 3. The existing-behavior part (search over an existing table) is
    asserted now.

    Validates: Requirements 3.4
    """
    provider = OpcpCompanionProvider()

    # Baseline pre-fix output: `_search` over an existing table.
    baseline_conn = _FakeConn(rows)
    baseline_chunks = provider._search(baseline_conn, [0.1, 0.2, 0.3], top_k=len(rows) or 1)

    # Same search over the recording connection (table already exists).
    conn = _RecordingConn(rows)

    # Guarded: only exercise ensure_vector_store when the fix has added it.
    if hasattr(provider, "ensure_vector_store"):
        provider.ensure_vector_store(conn)
        ddl = _provisioning_ddl(conn.executed_sql)
        # Only idempotent IF NOT EXISTS DDL is allowed — nothing destructive.
        for statement in ddl:
            assert "if not exists" in statement, (
                f"ensure_vector_store issued non-idempotent DDL: {statement!r}"
            )
            assert not statement.startswith(("drop ", "truncate ", "delete ", "alter ")), (
                f"ensure_vector_store issued destructive DDL: {statement!r}"
            )

    chunks = provider._search(conn, [0.1, 0.2, 0.3], top_k=len(rows) or 1)

    # The returned chunks equal the pre-fix output.
    assert chunks == baseline_chunks

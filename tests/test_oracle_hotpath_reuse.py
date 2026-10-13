"""Hot-path reuse tests for the Oracle providers (oracle-speedup Task 3 + 4).

These assert the latency-oriented behavior changes without caching answers:

Task 3 — OpcpCompanionProvider:
- the per-query hot path does NOT run the ``CREATE EXTENSION/TABLE`` DDL once
  the store has already been provisioned;
- provisioning runs exactly once across two consecutive queries;
- the borrowed pgvector connection is returned to the pool on both success and
  failure (never closed-by-caller when pooled, discarded when broken);
- the response contract (incl. ``sources``) is preserved.

Task 4 — app lifespan:
- startup invokes ``warmup_oracle_resources`` and a warmup failure never blocks
  startup; shutdown invokes ``dispose_all``.

All clients, the pool and connections are mocked — no real network/DB.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.oracle import resources
from app.oracle.ai_providers import OpcpCompanionProvider


@pytest.fixture(autouse=True)
def _clean_resources():
    resources.dispose_all()
    yield
    resources.dispose_all()


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _RecordingCursor:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        self._conn.executed_sql.append(" ".join(sql.split()).lower())
        return None

    def fetchall(self):
        return list(self._conn.rows)

    def close(self):
        return None


class _RecordingConn:
    """Connection to an already-provisioned vector DB."""

    def __init__(self, rows):
        self.rows = rows
        self.executed_sql = []
        self.commits = 0
        self.closed = False

    def cursor(self):
        return _RecordingCursor(self)

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


class _FakePool:
    """Minimal pool recording getconn/putconn so reuse can be asserted."""

    def __init__(self, conn):
        self._conn = conn
        self.borrowed = 0
        self.returned = []  # list of (conn, close) tuples

    def getconn(self):
        self.borrowed += 1
        return self._conn

    def putconn(self, conn, close=False):
        self.returned.append((conn, close))

    def closeall(self):
        pass


def _provider_with_tokens():
    provider = OpcpCompanionProvider()
    provider.embed_token = "embed-tok"
    provider.llm_token = "llm-tok"
    return provider


def _mock_clients(provider):
    embed_client = MagicMock()
    embed_client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.0] * provider.embedding_dim)]
    )
    llm_client = MagicMock()
    llm_client.responses.create.return_value = SimpleNamespace(
        output_text="Réponse simulée.",
        usage=SimpleNamespace(total_tokens=42),
    )
    return embed_client, llm_client


# ---------------------------------------------------------------------------
# Task 3 — no DDL in the hot path once provisioned
# ---------------------------------------------------------------------------

def test_hot_path_skips_ddl_when_already_provisioned(monkeypatch):
    """When the store is already provisioned, query() issues no CREATE DDL."""
    provider = _provider_with_tokens()
    embed_client, llm_client = _mock_clients(provider)
    conn = _RecordingConn([("Titre", "chemin.md", 0, "contenu", 0.9)])
    pool = _FakePool(conn)

    # Simulate a prior warmup/provisioning.
    resources.mark_vector_store_provisioned()

    with patch.object(provider, "_get_embed_client", return_value=embed_client), \
         patch.object(provider, "_get_llm_client", return_value=llm_client), \
         patch.object(resources, "_pg_pool", pool), \
         patch.object(provider, "_get_pg_connection", lambda: pool.getconn()):
        result = asyncio.run(provider.query("une question"))

    ddl = [s for s in conn.executed_sql if s.startswith(("create extension", "create table"))]
    assert ddl == [], f"hot path issued provisioning DDL: {ddl!r}"
    # A SELECT still ran (search happened).
    assert any(s.startswith("select") for s in conn.executed_sql)
    assert result["provider"] == "opcp_companion"
    assert result["sources"] == [
        {"title": "Titre", "file_path": "chemin.md", "similarity": 0.9}
    ]
    # Connection returned to the pool (not broken) exactly once.
    assert len(pool.returned) == 1
    assert pool.returned[0][0] is conn
    assert pool.returned[0][1] is False
    assert conn.closed is False  # pooled conn is not closed by the caller


def test_provisioning_runs_exactly_once_across_two_queries(monkeypatch):
    """First query provisions (DDL before SELECT); second query skips DDL."""
    provider = _provider_with_tokens()
    embed_client, llm_client = _mock_clients(provider)
    conn = _RecordingConn([("t", "f", 0, "c", 0.9)])
    pool = _FakePool(conn)

    assert resources.is_vector_store_provisioned() is False

    with patch.object(provider, "_get_embed_client", return_value=embed_client), \
         patch.object(provider, "_get_llm_client", return_value=llm_client), \
         patch.object(resources, "_pg_pool", pool), \
         patch.object(provider, "_get_pg_connection", lambda: pool.getconn()):
        asyncio.run(provider.query("q1"))
        first_ddl_count = sum(
            s.startswith(("create extension", "create table"))
            for s in conn.executed_sql
        )
        asyncio.run(provider.query("q2"))

    total_ext = sum(s.startswith("create extension") for s in conn.executed_sql)
    total_tbl = sum(s.startswith("create table") for s in conn.executed_sql)

    # Provisioning happened on the first query...
    assert first_ddl_count >= 2  # one extension + one table
    # ...and did not repeat on the second query.
    assert total_ext == 1
    assert total_tbl == 1
    assert resources.is_vector_store_provisioned() is True
    # Both queries borrowed and returned a connection.
    assert pool.borrowed == 2
    assert len(pool.returned) == 2


def test_connection_returned_as_broken_on_search_failure():
    """If the search raises, the pooled connection is returned with close=True."""
    provider = _provider_with_tokens()
    embed_client, llm_client = _mock_clients(provider)
    conn = _RecordingConn([("t", "f", 0, "c", 0.9)])
    pool = _FakePool(conn)
    resources.mark_vector_store_provisioned()

    def _boom(*a, **k):
        raise Exception("search exploded")

    with patch.object(provider, "_get_embed_client", return_value=embed_client), \
         patch.object(provider, "_get_llm_client", return_value=llm_client), \
         patch.object(resources, "_pg_pool", pool), \
         patch.object(provider, "_get_pg_connection", lambda: pool.getconn()), \
         patch.object(provider, "_search", side_effect=_boom):
        with pytest.raises(Exception):
            asyncio.run(provider.query("une question"))

    assert len(pool.returned) == 1
    assert pool.returned[0][1] is True  # discarded as broken


def test_release_without_pool_closes_connection_directly():
    """When no pool exists (e.g. test conn), release closes the conn directly."""
    provider = _provider_with_tokens()
    conn = _RecordingConn([])
    assert resources.peek_pg_pool() is None
    provider._release_pg_connection(conn, broken=False)
    assert conn.closed is True


# ---------------------------------------------------------------------------
# Task 4 — lifespan warmup / dispose wiring
# ---------------------------------------------------------------------------

def test_lifespan_warms_up_and_disposes(monkeypatch):
    """Starting the app invokes warmup; stopping it invokes dispose_all."""
    from fastapi.testclient import TestClient
    import app.oracle.resources as resources_module
    from app.main import app

    warmup = MagicMock()
    dispose = MagicMock()
    monkeypatch.setattr(resources_module, "warmup_oracle_resources", warmup)
    monkeypatch.setattr(resources_module, "dispose_all", dispose)

    with TestClient(app):
        assert warmup.call_count == 1
        assert dispose.call_count == 0

    # Context exit triggers lifespan shutdown.
    assert dispose.call_count == 1


def test_lifespan_warmup_failure_does_not_block_startup(monkeypatch):
    """A warmup exception is swallowed; the app still starts and serves."""
    from fastapi.testclient import TestClient
    import app.oracle.resources as resources_module
    from app.main import app

    def _warmup_boom():
        raise Exception("warmup failed")

    monkeypatch.setattr(resources_module, "warmup_oracle_resources", _warmup_boom)
    monkeypatch.setattr(resources_module, "dispose_all", MagicMock())

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200

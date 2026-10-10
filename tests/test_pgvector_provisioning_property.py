"""Property-based test for vector store provisioning idempotency.

Feature: pgvector-doc-embeddings
Property 1: Vector store provisioning is idempotent
Validates: Requirements 3.1, 3.2, 3.3, 3.4

This Hypothesis-driven property exercises
``OpcpCompanionProvider.ensure_vector_store`` (in ``app/oracle/ai_providers.py``)
by invoking it a varying number of times (1..20) against a *stateful* fake
connection/cursor that records every DDL statement and models the vector store
as a set of created objects.

The fake cursor honours ``IF NOT EXISTS`` semantics: re-issuing
``CREATE EXTENSION IF NOT EXISTS vector`` or ``CREATE TABLE IF NOT EXISTS
md_embeddings (...)`` when the object already exists is a no-op and never raises
(mirroring PostgreSQL). This lets the test assert the two idempotency
guarantees regardless of how many times provisioning runs:

- After N invocations the recorded DDL shows both the ``vector`` extension
  (Req 3.1) and the ``md_embeddings`` table (Req 3.2) were provisioned, and the
  final Vector_Store state is the same as after a single run (Req 3.3).
- All provisioning DDL uses ``IF NOT EXISTS`` so repeats never error (Req 3.3),
  and the ``embedding`` column is declared with the configured EMBEDDING_DIM of
  4096 (Req 3.4).

This test is complementary to the guarded idempotency coverage already present
in ``tests/test_opcp_companion_provider.py``: it uses its own distinct,
state-modelling fake connection and drives the invocation count with Hypothesis.
"""
import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.oracle.ai_providers import OpcpCompanionProvider


class _FakeCursor:
    """Records executed DDL and models IF NOT EXISTS create semantics.

    Shares the parent connection's ``store`` (set of created object names) and
    ``executed_sql`` (ordered list of every statement issued) so that state
    persists across the ``cursor()`` calls made by successive
    ``ensure_vector_store`` invocations.
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        self._conn.executed_sql.append(sql)
        normalized = " ".join(sql.split()).lower()

        # CREATE EXTENSION IF NOT EXISTS vector
        if normalized.startswith("create extension"):
            assert "if not exists" in normalized, (
                f"ensure_vector_store issued non-idempotent extension DDL: {sql!r}"
            )
            # Idempotent: creating an already-present extension is a no-op.
            self._conn.store.add("extension:vector")
            return None

        # CREATE TABLE IF NOT EXISTS md_embeddings (...)
        if normalized.startswith("create table"):
            assert "if not exists" in normalized, (
                f"ensure_vector_store issued non-idempotent table DDL: {sql!r}"
            )
            self._conn.store.add("table:md_embeddings")
            return None

        # Anything destructive would break idempotency guarantees.
        assert not normalized.startswith(("drop ", "truncate ", "delete ", "alter ")), (
            f"ensure_vector_store issued destructive DDL: {sql!r}"
        )
        return None

    def close(self):
        return None


class _FakeConn:
    """Stateful fake psycopg2 connection recording DDL and commits."""

    def __init__(self):
        self.store = set()
        self.executed_sql = []
        self.commits = 0

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.commits += 1


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(invocations=st.integers(min_value=1, max_value=20))
def test_vector_store_provisioning_is_idempotent(invocations):
    """Property 1: repeated ``ensure_vector_store`` is idempotent (Req 3.1-3.4)."""
    provider = OpcpCompanionProvider()
    conn = _FakeConn()

    # Invoke provisioning N times; no invocation may raise (Req 3.3).
    for _ in range(invocations):
        provider.ensure_vector_store(conn)

    # --- Req 3.1: the vector extension was provisioned. ---
    assert "extension:vector" in conn.store, (
        f"vector extension never provisioned. Executed SQL: {conn.executed_sql!r}"
    )
    assert any(
        " ".join(s.split()).lower().startswith("create extension")
        and "vector" in " ".join(s.split()).lower()
        for s in conn.executed_sql
    )

    # --- Req 3.2: the md_embeddings table was provisioned. ---
    assert "table:md_embeddings" in conn.store, (
        f"md_embeddings table never provisioned. Executed SQL: {conn.executed_sql!r}"
    )
    assert any(
        " ".join(s.split()).lower().startswith("create table")
        and "md_embeddings" in " ".join(s.split()).lower()
        for s in conn.executed_sql
    )

    # --- Req 3.3: final Vector_Store state is identical regardless of count. ---
    # The store models the provisioned objects; N runs converge on the same set
    # a single run produces.
    assert conn.store == {"extension:vector", "table:md_embeddings"}

    # Every issued statement is idempotent DDL (IF NOT EXISTS), so repeats never
    # error. Also assert one commit per invocation (durable, side-effect free).
    for statement in conn.executed_sql:
        normalized = " ".join(statement.split()).lower()
        assert "if not exists" in normalized, (
            f"non-idempotent DDL would error on repeat: {statement!r}"
        )
    assert conn.commits == invocations

    # --- Req 3.4: embedding column declared with EMBEDDING_DIM == 4096. ---
    create_table = next(
        s for s in conn.executed_sql
        if " ".join(s.split()).lower().startswith("create table")
    )
    dim_match = re.search(r"embedding\s+vector\((\d+)\)", create_table, re.IGNORECASE)
    assert dim_match is not None, (
        f"embedding column dimension not declared: {create_table!r}"
    )
    assert int(dim_match.group(1)) == provider.embedding_dim == 4096

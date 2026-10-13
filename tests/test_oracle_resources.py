"""Tests for the shared Oracle resource layer (app/oracle/resources.py).

Feature: oracle-speedup — Task 1.

The resource layer builds the Shai HTTP client, the OVH embedding/LLM clients,
and the pgvector connection pool once and reuses them across requests. These
tests assert:

- each accessor returns the SAME instance across calls (reuse / caching);
- the clients/pool are built from ``settings`` (no user input), with the LLM
  endpoint falling back to the embedding endpoint;
- ``dispose_all`` tears everything down and resets the singletons so the next
  accessor rebuilds;
- a missing ``SHAI_API_KEY`` short-circuits with a clear French error;
- the one-time vector-store provisioning flag flips exactly once.

All external constructors (OpenAI client, psycopg2 pool) are mocked — no real
network or DB access.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.oracle import resources


@pytest.fixture(autouse=True)
def _clean_resources():
    """Each test starts and ends with a clean resource module state."""
    resources.dispose_all()
    yield
    resources.dispose_all()


# ---------------------------------------------------------------------------
# Accessor reuse / identity
# ---------------------------------------------------------------------------

def test_shai_client_is_built_once_and_reused():
    build = MagicMock(return_value=MagicMock(name="shai-client"))
    with patch.object(resources.settings, "SHAI_API_KEY", "k"), \
         patch.object(resources.settings, "SHAI_API_URL", "https://shai.example/v1"), \
         patch.object(resources, "_build_openai_client", build):
        first = resources.get_shai_client()
        second = resources.get_shai_client()

    assert first is second
    build.assert_called_once_with(base_url="https://shai.example/v1", api_key="k")


def test_embed_client_is_built_once_and_reused():
    build = MagicMock(return_value=MagicMock(name="embed-client"))
    with patch.object(resources.settings, "OVH_AI_ENDPOINT", "https://embed.example/v1"), \
         patch.object(resources.settings, "OVH_AI_TOKEN", "embed-tok"), \
         patch.object(resources, "_build_openai_client", build):
        first = resources.get_embed_client()
        second = resources.get_embed_client()

    assert first is second
    build.assert_called_once_with(
        base_url="https://embed.example/v1", api_key="embed-tok"
    )


def test_llm_client_falls_back_to_embedding_endpoint_and_token():
    build = MagicMock(return_value=MagicMock(name="llm-client"))
    with patch.object(resources.settings, "LLM_ENDPOINT", ""), \
         patch.object(resources.settings, "LLM_TOKEN", ""), \
         patch.object(resources.settings, "OVH_AI_ENDPOINT", "https://embed.example/v1"), \
         patch.object(resources.settings, "OVH_AI_TOKEN", "embed-tok"), \
         patch.object(resources, "_build_openai_client", build):
        client = resources.get_llm_client()
        again = resources.get_llm_client()

    assert client is again
    build.assert_called_once_with(
        base_url="https://embed.example/v1", api_key="embed-tok"
    )


def test_llm_client_uses_dedicated_llm_settings_when_present():
    build = MagicMock(return_value=MagicMock(name="llm-client"))
    with patch.object(resources.settings, "LLM_ENDPOINT", "https://llm.example/v1"), \
         patch.object(resources.settings, "LLM_TOKEN", "llm-tok"), \
         patch.object(resources, "_build_openai_client", build):
        resources.get_llm_client()

    build.assert_called_once_with(base_url="https://llm.example/v1", api_key="llm-tok")


def test_pg_pool_is_built_once_with_settings_and_reused():
    fake_pool = MagicMock(name="pool")
    pool_ctor = MagicMock(return_value=fake_pool)
    fake_psycopg2_pool = SimpleNamespace(SimpleConnectionPool=pool_ctor)

    import sys
    with patch.object(resources.settings, "PG_HOST", "pg.example"), \
         patch.object(resources.settings, "PG_PORT", 5432), \
         patch.object(resources.settings, "PG_DB", "db"), \
         patch.object(resources.settings, "PG_USER", "user"), \
         patch.object(resources.settings, "PG_PASSWORD", "secret"), \
         patch.dict(sys.modules, {"psycopg2.pool": fake_psycopg2_pool}):
        first = resources.get_pg_pool()
        second = resources.get_pg_pool()

    assert first is second is fake_pool
    pool_ctor.assert_called_once()
    _args, kwargs = pool_ctor.call_args
    assert kwargs["host"] == "pg.example"
    assert kwargs["dbname"] == "db"
    assert kwargs["user"] == "user"
    assert kwargs["password"] == "secret"


# ---------------------------------------------------------------------------
# Missing configuration
# ---------------------------------------------------------------------------

def test_get_shai_client_missing_key_raises_french_error():
    with patch.object(resources.settings, "SHAI_API_KEY", ""):
        with pytest.raises(Exception) as exc:
            resources.get_shai_client()
    assert "SHAI_API_KEY" in str(exc.value)


# ---------------------------------------------------------------------------
# dispose_all resets the singletons and closes resources
# ---------------------------------------------------------------------------

def test_dispose_all_closes_clients_and_pool_and_resets():
    shai = MagicMock(name="shai")
    embed = MagicMock(name="embed")
    llm = MagicMock(name="llm")
    fake_pool = MagicMock(name="pool")

    build = MagicMock(side_effect=[shai, embed, llm])
    pool_ctor = MagicMock(return_value=fake_pool)
    fake_psycopg2_pool = SimpleNamespace(SimpleConnectionPool=pool_ctor)

    import sys
    with patch.object(resources.settings, "SHAI_API_KEY", "k"), \
         patch.object(resources.settings, "OVH_AI_TOKEN", "t"), \
         patch.object(resources, "_build_openai_client", build), \
         patch.dict(sys.modules, {"psycopg2.pool": fake_psycopg2_pool}):
        resources.get_shai_client()
        resources.get_embed_client()
        resources.get_llm_client()
        resources.get_pg_pool()

        resources.dispose_all()

    shai.close.assert_called_once()
    embed.close.assert_called_once()
    llm.close.assert_called_once()
    fake_pool.closeall.assert_called_once()

    # After dispose, a fresh accessor rebuilds (singletons were reset).
    assert resources.peek_pg_pool() is None
    build2 = MagicMock(return_value=MagicMock())
    with patch.object(resources.settings, "SHAI_API_KEY", "k"), \
         patch.object(resources, "_build_openai_client", build2):
        resources.get_shai_client()
    build2.assert_called_once()


# ---------------------------------------------------------------------------
# One-time vector-store provisioning flag
# ---------------------------------------------------------------------------

def test_provisioned_flag_round_trips():
    assert resources.is_vector_store_provisioned() is False
    resources.mark_vector_store_provisioned()
    assert resources.is_vector_store_provisioned() is True
    resources.dispose_all()
    assert resources.is_vector_store_provisioned() is False


def test_peek_pg_pool_does_not_construct_pool():
    assert resources.peek_pg_pool() is None  # no construction, no DB access

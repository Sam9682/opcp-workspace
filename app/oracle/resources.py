"""Shared, reusable resources for the Oracle AI providers.

Rationale (performance): previously every Oracle query paid a cold-start cost —
the Shai path spawned a one-shot ``shai`` subprocess, and the OPCP Companion RAG
path built a fresh OpenAI embedding client, a fresh LLM client and a brand-new
psycopg2 connection on *every* call (and ran the ``CREATE EXTENSION/TABLE`` DDL
in the hot path). This module centralises those resources as process-wide,
lazily-created singletons so they are built once and reused across requests:

- a shared Shai HTTP client (OpenAI-compatible, pointing at ``SHAI_API_URL``);
- a shared OVH embedding client;
- a shared OVH LLM client;
- a small pooled psycopg2 connection pool for pgvector.

Everything is sourced from :data:`app.config.settings` (never user input).
Accessors are cheap and idempotent; :func:`warmup_oracle_resources` builds the
configured resources ahead of the first request and :func:`dispose_all` tears
them down on shutdown. No answers are cached here — only the clients/connection
machinery is reused, so answers stay fresh.

Single container / single process: in-process singletons + a tiny pool are
sufficient; there is no cross-process shared cache (no Redis).
"""
from __future__ import annotations

import threading
from typing import Any, Optional

from app.config import settings
from app.logging_config import logger


# Pool sizing for a single container / single worker process. One always-open
# connection with a small headroom for brief concurrency.
_PG_POOL_MIN = 1
_PG_POOL_MAX = 4


# ---------------------------------------------------------------------------
# Module-level singletons (guarded by a re-entrant lock so first-use from
# concurrent requests builds each resource exactly once).
# ---------------------------------------------------------------------------
_lock = threading.RLock()

_shai_client: Optional[Any] = None
_embed_client: Optional[Any] = None
_llm_client: Optional[Any] = None
_pg_pool: Optional[Any] = None


def _build_openai_client(base_url: str, api_key: str) -> Any:
    """Construct an OpenAI-compatible client (OVH AI Endpoints / Shai).

    Imported lazily so importing this module never requires the ``openai``
    package to be installed (mirrors the lazy import already used by the
    providers).
    """
    from openai import OpenAI

    return OpenAI(base_url=base_url, api_key=api_key)


# ---------------------------------------------------------------------------
# Accessors — each builds its resource once and reuses it thereafter.
# ---------------------------------------------------------------------------
def get_shai_client() -> Any:
    """Return the shared Shai HTTP client (OpenAI-compatible).

    Built from ``settings.SHAI_API_URL`` + ``settings.SHAI_API_KEY``. Raises a
    clear French configuration error when the key is missing so callers never
    construct an unusable client.
    """
    global _shai_client
    if _shai_client is not None:
        return _shai_client
    with _lock:
        if _shai_client is None:
            if not settings.SHAI_API_KEY:
                raise Exception(
                    "Configuration manquante : SHAI_API_KEY est requis pour "
                    "interroger le fournisseur Shai."
                )
            _shai_client = _build_openai_client(
                base_url=settings.SHAI_API_URL,
                api_key=settings.SHAI_API_KEY,
            )
    return _shai_client


def get_embed_client() -> Any:
    """Return the shared OVH embedding client (OpenAI-compatible)."""
    global _embed_client
    if _embed_client is not None:
        return _embed_client
    with _lock:
        if _embed_client is None:
            _embed_client = _build_openai_client(
                base_url=settings.OVH_AI_ENDPOINT,
                api_key=settings.OVH_AI_TOKEN,
            )
    return _embed_client


def get_llm_client() -> Any:
    """Return the shared OVH LLM client (OpenAI-compatible).

    Falls back to the embedding endpoint/token when the dedicated ``LLM_*``
    settings are empty, matching the provider's original behaviour.
    """
    global _llm_client
    if _llm_client is not None:
        return _llm_client
    with _lock:
        if _llm_client is None:
            _llm_client = _build_openai_client(
                base_url=settings.LLM_ENDPOINT or settings.OVH_AI_ENDPOINT,
                api_key=settings.LLM_TOKEN or settings.OVH_AI_TOKEN,
            )
    return _llm_client


def peek_pg_pool() -> Optional[Any]:
    """Return the current pgvector pool without constructing one.

    Returns ``None`` when no pool has been created yet. Used by connection
    release so returning a non-pooled (e.g. test) connection never triggers a
    real pool/DB connection.
    """
    return _pg_pool


def get_pg_pool() -> Any:
    """Return the shared pgvector connection pool.

    A :class:`psycopg2.pool.SimpleConnectionPool` sized for one container.
    Connections are borrowed with :func:`get_pg_pool().getconn` and must be
    returned with ``putconn`` (see :class:`PooledConnection`).
    """
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    with _lock:
        if _pg_pool is None:
            from psycopg2.pool import SimpleConnectionPool

            _pg_pool = SimpleConnectionPool(
                _PG_POOL_MIN,
                _PG_POOL_MAX,
                host=settings.PG_HOST,
                port=settings.PG_PORT,
                dbname=settings.PG_DB,
                user=settings.PG_USER,
                password=settings.PG_PASSWORD,
            )
    return _pg_pool


class PooledConnection:
    """Context manager that borrows a connection from the pgvector pool.

    Guarantees the connection is returned to the pool on exit, including when
    the ``with`` body raises. Broken connections are returned with
    ``close=True`` so the pool discards them instead of reusing a bad socket.
    """

    def __init__(self) -> None:
        self._pool = get_pg_pool()
        self._conn: Optional[Any] = None

    def __enter__(self) -> Any:
        self._conn = self._pool.getconn()
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._conn is not None:
            try:
                self._pool.putconn(self._conn, close=exc_type is not None)
            except Exception:  # pragma: no cover - defensive; never mask body
                pass
            self._conn = None
        return False


def warmup_oracle_resources() -> None:
    """Build the configured shared resources ahead of the first request.

    Each resource is attempted independently and best-effort: a resource whose
    required configuration is absent (e.g. no ``SHAI_API_KEY`` or no
    ``OVH_AI_TOKEN``) is skipped with a debug note rather than failing warmup.
    The pgvector store is also provisioned once here (``ensure_vector_store``)
    so the per-query hot path no longer runs the ``CREATE EXTENSION/TABLE`` DDL.

    This function never raises: callers (app startup) stay decoupled from
    optional provider configuration.
    """
    # Shai HTTP client (only if a key is configured).
    if settings.SHAI_API_KEY:
        try:
            get_shai_client()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Oracle warmup: Shai client unavailable ({exc}).")
    else:
        logger.debug("Oracle warmup: SHAI_API_KEY absent, Shai client skipped.")

    # OVH embedding + LLM clients and pgvector pool (only if a token is set).
    if settings.OVH_AI_TOKEN or settings.LLM_TOKEN:
        try:
            get_embed_client()
            get_llm_client()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Oracle warmup: OVH clients unavailable ({exc}).")

        try:
            get_pg_pool()
            _provision_vector_store_once()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                f"Oracle warmup: pgvector pool/provisioning unavailable ({exc})."
            )
    else:
        logger.debug(
            "Oracle warmup: OVH_AI_TOKEN/LLM_TOKEN absent, RAG resources skipped."
        )

    logger.info("Oracle resources warmed up")


# ---------------------------------------------------------------------------
# One-time pgvector provisioning (lifted out of the per-query hot path).
# ---------------------------------------------------------------------------
_provisioned = False


def is_vector_store_provisioned() -> bool:
    """Whether the pgvector store has already been provisioned this process."""
    return _provisioned


def mark_vector_store_provisioned() -> None:
    """Record that the pgvector store has been provisioned this process."""
    global _provisioned
    with _lock:
        _provisioned = True


def _provision_vector_store_once() -> None:
    """Run ``ensure_vector_store`` at most once per process (warmup path).

    Borrows a pooled connection and delegates to the provider's idempotent
    provisioning DDL, then records the one-time flag so the per-query hot path
    skips the DDL. Subsequent calls are no-ops. Imported lazily to avoid a
    circular import with ``ai_providers``.
    """
    if _provisioned:
        return
    with _lock:
        if _provisioned:
            return
        from app.oracle.ai_providers import OpcpCompanionProvider

        provider = OpcpCompanionProvider()
        with PooledConnection() as conn:
            provider.ensure_vector_store(conn)
    mark_vector_store_provisioned()


def dispose_all() -> None:
    """Dispose all shared resources and reset the singletons.

    Closes OpenAI-compatible clients when they expose ``close`` and closes the
    pgvector pool. Called on application shutdown. Also resets the one-time
    provisioning flag so a fresh warmup re-provisions after a restart within the
    same process (e.g. in tests).
    """
    global _shai_client, _embed_client, _llm_client, _pg_pool, _provisioned
    with _lock:
        for client in (_shai_client, _embed_client, _llm_client):
            close = getattr(client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # pragma: no cover - defensive
                    pass
        if _pg_pool is not None:
            try:
                _pg_pool.closeall()
            except Exception:  # pragma: no cover - defensive
                pass
        _shai_client = None
        _embed_client = None
        _llm_client = None
        _pg_pool = None
        _provisioned = False

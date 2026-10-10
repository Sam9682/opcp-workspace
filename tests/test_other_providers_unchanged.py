"""Regression tests asserting non-Shai providers are unchanged (task 6.1).

Feature spec: .kiro/specs/shai-ia-context

The skill-context injection is scoped exclusively to ``ShaiAIProvider``. These
tests verify that ``KiroAIProvider``, ``OpenAIProvider``, and
``OpcpCompanionProvider``:

- never invoke the skill-context loader ``_load_shai_skill_context``; and
- assemble their prompts / messages exactly as they did before the feature.

External calls (subprocess, httpx, the RAG pipeline) are mocked so the tests
stay focused on prompt/message assembly.

Requirements: 2.5
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.oracle.ai_providers as ai_providers
from app.oracle.ai_providers import (
    KiroAIProvider,
    OpenAIProvider,
    OpcpCompanionProvider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _guard_skill_loader(monkeypatch):
    """Replace ``_load_shai_skill_context`` with a spy that fails if called.

    Returns the spy so tests can assert it was never invoked. The scope of the
    feature (Req 2.5) is that only the Shai provider reads the skill context, so
    any call from another provider is a scope violation.
    """
    spy = MagicMock(name="_load_shai_skill_context")
    monkeypatch.setattr(ai_providers, "_load_shai_skill_context", spy)
    return spy


class _FakeProcess:
    """Minimal stand-in for an asyncio subprocess with a captured prompt."""

    def __init__(self, stdout: bytes = b"reponse", stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self):
        return self._stdout, self._stderr

    def kill(self):  # pragma: no cover - only used on timeout paths
        pass


# ===========================================================================
# KiroAIProvider
# ===========================================================================

def test_kiro_provider_does_not_read_skill_context_and_uses_bare_question(monkeypatch):
    """Without context, Kiro sends the bare ``question`` and never loads the
    skill context."""
    spy = _guard_skill_loader(monkeypatch)
    captured = {}

    async def fake_exec(*args, **kwargs):
        # args = ('kiro-cli', 'chat', '--no-interactive', '--trust-all-tools', prompt)
        captured["args"] = args
        return _FakeProcess(stdout=b"une reponse kiro")

    monkeypatch.setattr(ai_providers.asyncio, "create_subprocess_exec", fake_exec)

    result = asyncio.run(KiroAIProvider().query("Quelle heure est-il ?"))

    prompt = captured["args"][-1]
    assert prompt == "Quelle heure est-il ?"
    assert result["provider"] == "kiro"
    spy.assert_not_called()


def test_kiro_provider_uses_legacy_context_prompt_form(monkeypatch):
    """With context, Kiro keeps its legacy ``Contexte: ...\\n\\nQuestion: ...``
    form and never loads the skill context."""
    spy = _guard_skill_loader(monkeypatch)
    captured = {}

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        return _FakeProcess(stdout=b"une reponse kiro")

    monkeypatch.setattr(ai_providers.asyncio, "create_subprocess_exec", fake_exec)

    asyncio.run(KiroAIProvider().query("Ma question", context="Mon contexte"))

    prompt = captured["args"][-1]
    assert prompt == "Contexte: Mon contexte\n\nQuestion: Ma question"
    spy.assert_not_called()


# ===========================================================================
# OpenAIProvider
# ===========================================================================

def _openai_response_payload():
    return {
        "choices": [{"message": {"content": "reponse openai"}}],
        "usage": {"total_tokens": 42},
    }


def _make_openai_client_mock(captured):
    """Build an async-context-manager httpx client mock that records the JSON body."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=_openai_response_payload())

    async def fake_post(url, **kwargs):
        captured["json"] = kwargs.get("json")
        return response

    client = MagicMock()
    client.post = AsyncMock(side_effect=fake_post)

    async_cm = MagicMock()
    async_cm.__aenter__ = AsyncMock(return_value=client)
    async_cm.__aexit__ = AsyncMock(return_value=False)
    return async_cm


def test_openai_provider_builds_user_only_messages_without_context(monkeypatch):
    """Without context, OpenAI sends a single user-role message and never loads
    the skill context."""
    spy = _guard_skill_loader(monkeypatch)
    captured = {}

    provider = OpenAIProvider()
    provider.api_key = "test-key"

    monkeypatch.setattr(
        ai_providers.httpx, "AsyncClient", lambda *a, **k: _make_openai_client_mock(captured)
    )

    result = asyncio.run(provider.query("Ma question"))

    assert captured["json"]["messages"] == [
        {"role": "user", "content": "Ma question"},
    ]
    assert result["provider"] == "openai"
    spy.assert_not_called()


def test_openai_provider_builds_system_and_user_messages_with_context(monkeypatch):
    """With context, OpenAI sends a system-role context message followed by the
    user question, and never loads the skill context."""
    spy = _guard_skill_loader(monkeypatch)
    captured = {}

    provider = OpenAIProvider()
    provider.api_key = "test-key"

    monkeypatch.setattr(
        ai_providers.httpx, "AsyncClient", lambda *a, **k: _make_openai_client_mock(captured)
    )

    asyncio.run(provider.query("Ma question", context="Mon contexte"))

    assert captured["json"]["messages"] == [
        {"role": "system", "content": "Mon contexte"},
        {"role": "user", "content": "Ma question"},
    ]
    spy.assert_not_called()


# ===========================================================================
# OpcpCompanionProvider
# ===========================================================================

def test_opcp_companion_provider_does_not_read_skill_context(monkeypatch):
    """The RAG pipeline builds its prompt from retrieved chunks via SYSTEM_PROMPT
    and never loads the Shai skill context."""
    spy = _guard_skill_loader(monkeypatch)

    provider = OpcpCompanionProvider()
    provider.embed_token = "embed-token"
    provider.llm_token = "llm-token"

    chunks = [
        {"title": "Doc A", "file_path": "a.md", "chunk_index": 0, "content": "contenu A", "similarity": 0.9},
    ]

    captured = {}

    def fake_create(**kwargs):
        captured["instructions"] = kwargs.get("instructions")
        captured["input"] = kwargs.get("input")
        return SimpleNamespace(output_text="reponse rag", usage=None)

    llm_client = MagicMock()
    llm_client.responses.create = MagicMock(side_effect=fake_create)

    with patch.object(provider, "_get_embed_client", return_value=MagicMock()), \
         patch.object(provider, "_embed_query", return_value=[0.0] * provider.embedding_dim), \
         patch.object(provider, "_get_pg_connection", return_value=MagicMock()), \
         patch.object(provider, "ensure_vector_store", return_value=None), \
         patch.object(provider, "_search", return_value=chunks), \
         patch.object(provider, "_get_llm_client", return_value=llm_client):
        result = asyncio.run(provider.query("Ma question"))

    assert result["provider"] == "opcp_companion"
    # The generation instructions come from SYSTEM_PROMPT + retrieved context,
    # not from the Shai skill-context file.
    assert "OPCP Companion" in captured["instructions"]
    assert "contenu A" in captured["instructions"]
    assert captured["input"] == "Ma question"
    spy.assert_not_called()

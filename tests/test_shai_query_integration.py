"""Integration test for ``ShaiAIProvider.query()`` prompt assembly.

Feature: shai-ia-context (prompt assembly) + oracle-speedup (HTTP transport)

The Shai provider assembles the prompt from the (optional) skill context, the
(optional) existing context, and the user question, then sends it to the OVH
OpenAI-compatible chat endpoint (``settings.SHAI_API_URL``) through a
process-wide shared client (see ``app/oracle/resources.py``). This replaced the
former one-shot ``shai`` CLI subprocess, removing per-query cold-start.

These tests exercise the real ``query()`` code path end to end, replacing only
the shared HTTP client with a mock whose ``chat.completions.create`` records the
messages it receives and returns a canned answer. We capture the single user
message to assert the assembled prompt, for two cases:

(a) skill-context file present  -> prompt has skill context first, then
    ``Contexte:``, then ``Question:`` (combine, not replace).
(b) skill-context file missing   -> prompt degrades to existing context +
    question, no skill context, and ``query()`` still succeeds.

A regression assertion also verifies that NO subprocess is spawned on the Shai
path (the latency fix): ``asyncio.create_subprocess_exec`` must not be called.

Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.4 (prompt assembly); oracle-speedup.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app.oracle.ai_providers as ai_providers
from app.config import settings
from app.oracle.ai_providers import ShaiAIProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_shai_client(answer: str = "Reponse Shai simulee."):
    """Build a mock OpenAI-compatible client recording the created messages.

    ``chat.completions.create(...)`` records its kwargs on ``client.calls`` and
    returns a response shaped like the OpenAI SDK
    (``.choices[0].message.content`` + ``.usage.total_tokens``).
    """
    client = MagicMock()
    client.calls = []

    def _create(**kwargs):
        client.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=answer))],
            usage=SimpleNamespace(total_tokens=7),
        )

    client.chat.completions.create = MagicMock(side_effect=_create)
    return client


def _captured_prompt(client) -> str:
    """Extract the single user message content passed to the Shai client."""
    assert len(client.calls) == 1, (
        f"expected exactly one chat.completions.create call, got {len(client.calls)}"
    )
    messages = client.calls[0]["messages"]
    assert len(messages) == 1 and messages[0]["role"] == "user"
    return messages[0]["content"]


def _run_shai_query(provider, client, question, context=None):
    """Run query() with the shared client patched and a key configured."""
    no_subprocess = MagicMock(
        side_effect=AssertionError("Shai must not spawn a subprocess")
    )
    with patch.object(settings, "SHAI_API_KEY", "test-shai-key"), \
         patch.object(provider, "_get_client", return_value=client), \
         patch.object(ai_providers.asyncio, "create_subprocess_exec", no_subprocess):
        return asyncio.run(provider.query(question, context=context))


# ---------------------------------------------------------------------------
# Case (a): skill-context file present (Req 2.1, 2.2, 2.3, 2.4)
# ---------------------------------------------------------------------------

def test_query_prepends_skill_context_before_context_and_question(tmp_path, monkeypatch):
    """With a present skill-context file, the assembled prompt places the skill
    context first, then the existing ``Contexte:`` block, then ``Question:``.

    Validates: Requirements 2.1, 2.2, 2.3, 2.4
    """
    skill = "Contexte metier OPCP: lire ./docs/opcp_external_docs avant de repondre."
    ctx_file = tmp_path / "shai_context.md"
    ctx_file.write_text(skill + "\n", encoding="utf-8")
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(ctx_file))

    client = _make_fake_shai_client()
    provider = ShaiAIProvider()
    result = _run_shai_query(
        provider, client, "Comment provisionner un cluster ?", context="cluster de prod"
    )

    prompt = _captured_prompt(client)

    skill_pos = prompt.index(skill)
    context_block = "Contexte: cluster de prod"
    context_pos = prompt.index(context_block)
    question_block = "Question: Comment provisionner un cluster ?"
    question_pos = prompt.index(question_block)

    # Skill context first, then existing context, then question.
    assert skill_pos < context_pos < question_pos
    # Existing context is combined, not replaced: its text is retained.
    assert context_block in prompt
    # Exact assembly (skill + Contexte + Question joined with blank lines).
    assert prompt == f"{skill}\n\n{context_block}\n\n{question_block}"

    # query() completes and returns the provider payload from the HTTP client.
    assert result["provider"] == "shai"
    assert result["answer"] == "Reponse Shai simulee."
    # Endpoint model comes from settings.
    assert client.calls[0]["model"] == settings.SHAI_MODEL


def test_query_combines_skill_context_and_question_when_no_existing_context(
    tmp_path, monkeypatch
):
    """With a present skill-context file and no existing context, the prompt is
    skill context followed by the question (Req 2.4).

    Validates: Requirements 2.1, 2.2, 2.4
    """
    skill = "Domaine OPCP (On Premise Cloud Platform, OVH)."
    ctx_file = tmp_path / "shai_context.md"
    ctx_file.write_text(skill, encoding="utf-8")
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(ctx_file))

    client = _make_fake_shai_client()
    provider = ShaiAIProvider()
    result = _run_shai_query(provider, client, "Qu'est-ce qu'OPCP ?")

    prompt = _captured_prompt(client)

    question_block = "Question: Qu'est-ce qu'OPCP ?"
    assert prompt == f"{skill}\n\n{question_block}"
    # No existing-context block was injected.
    assert "Contexte:" not in prompt
    assert result["provider"] == "shai"


# ---------------------------------------------------------------------------
# Case (b): skill-context file missing (Req 3.1, 3.4)
# ---------------------------------------------------------------------------

def test_query_degrades_to_context_and_question_when_file_missing(tmp_path, monkeypatch):
    """With a missing skill-context file, the prompt degrades to existing
    context + question (no skill context) and ``query()`` still succeeds.

    Validates: Requirements 3.1, 3.4
    """
    missing = tmp_path / "does_not_exist.md"
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(missing))

    client = _make_fake_shai_client()
    provider = ShaiAIProvider()
    result = _run_shai_query(
        provider, client, "Comment sauvegarder ?", context="donnees critiques"
    )

    prompt = _captured_prompt(client)

    context_block = "Contexte: donnees critiques"
    question_block = "Question: Comment sauvegarder ?"
    # Only the existing context and the question remain, in that order.
    assert prompt == f"{context_block}\n\n{question_block}"
    # No skill-context section leaked in.
    assert prompt.startswith("Contexte:")

    assert result["provider"] == "shai"
    assert result["answer"] == "Reponse Shai simulee."


def test_query_degrades_to_question_only_when_file_missing_and_no_context(
    tmp_path, monkeypatch
):
    """Missing file and no existing context -> prompt is just the question, and
    ``query()`` succeeds (Req 3.1, 3.4)."""
    missing = tmp_path / "nope.md"
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(missing))

    client = _make_fake_shai_client()
    provider = ShaiAIProvider()
    result = _run_shai_query(provider, client, "Une simple question ?")

    prompt = _captured_prompt(client)

    assert prompt == "Question: Une simple question ?"
    assert "Contexte:" not in prompt
    assert result["provider"] == "shai"


# ---------------------------------------------------------------------------
# oracle-speedup: missing key -> clear French config error (no network)
# ---------------------------------------------------------------------------

def test_query_raises_french_config_error_when_key_missing():
    """With no SHAI_API_KEY, query() fails fast with a French config error and
    never builds/calls a client."""
    provider = ShaiAIProvider()
    client = _make_fake_shai_client()
    with patch.object(settings, "SHAI_API_KEY", ""), \
         patch.object(provider, "_get_client", return_value=client):
        try:
            asyncio.run(provider.query("Une question ?"))
            raised = None
        except Exception as exc:  # noqa: BLE001 - asserting on message
            raised = str(exc)

    assert raised is not None
    assert "SHAI_API_KEY" in raised
    # No client call happened.
    assert client.calls == []

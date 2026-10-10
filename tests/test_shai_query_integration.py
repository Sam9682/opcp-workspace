"""Integration test for ``ShaiAIProvider.query()`` prompt assembly.

Feature: shai-ia-context

Covers optional test task:
- 6.2  Integration test for `ShaiAIProvider.query()` prompt assembly

The Shai provider assembles the prompt from the (optional) skill context, the
(optional) existing context, and the user question, then sends it as the single
positional argument to the ``shai`` CLI via
``asyncio.create_subprocess_exec('shai', prompt, ...)``.

These tests exercise the real ``query()`` code path end to end, replacing only
the subprocess boundary with an ``AsyncMock`` whose fake process returns clean
stdout, empty stderr, and returncode 0. We capture the positional args passed to
the CLI to assert the assembled prompt, for two cases:

(a) skill-context file present  -> prompt has skill context first, then
    ``Contexte:``, then ``Question:`` (combine, not replace).
(b) skill-context file missing   -> prompt degrades to existing context +
    question, no skill context, and ``query()`` still succeeds.

``app/oracle/ai_providers.py`` is not modified.

Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.4
"""
import asyncio
from unittest.mock import AsyncMock, patch

import app.oracle.ai_providers as ai_providers
from app.oracle.ai_providers import ShaiAIProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_subprocess(stdout: bytes = b"Reponse Shai simulee.", returncode: int = 0):
    """Build an AsyncMock replacing ``asyncio.create_subprocess_exec``.

    The mock records the positional args of each call and returns a fake process
    whose ``communicate()`` coroutine yields ``(stdout, b"")`` and whose
    ``returncode`` is ``returncode``. ``kill`` is a no-op.
    """
    fake_process = AsyncMock()
    fake_process.communicate.return_value = (stdout, b"")
    fake_process.returncode = returncode
    fake_process.kill = lambda: None

    create_mock = AsyncMock(return_value=fake_process)
    return create_mock


def _captured_prompt(create_mock) -> str:
    """Extract the prompt (2nd positional arg) passed to the Shai CLI."""
    assert create_mock.await_count == 1, (
        f"expected exactly one subprocess call, got {create_mock.await_count}"
    )
    args, _kwargs = create_mock.await_args
    # query() calls create_subprocess_exec('shai', prompt, ...)
    assert args[0] == "shai"
    return args[1]


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

    create_mock = _make_fake_subprocess()

    provider = ShaiAIProvider()
    with patch.object(ai_providers.asyncio, "create_subprocess_exec", create_mock):
        result = asyncio.run(
            provider.query("Comment provisionner un cluster ?", context="cluster de prod")
        )

    prompt = _captured_prompt(create_mock)

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

    # query() completes and returns the provider payload from the fake CLI.
    assert result["provider"] == "shai"
    assert result["answer"] == "Reponse Shai simulee."


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

    create_mock = _make_fake_subprocess()

    provider = ShaiAIProvider()
    with patch.object(ai_providers.asyncio, "create_subprocess_exec", create_mock):
        result = asyncio.run(provider.query("Qu'est-ce qu'OPCP ?"))

    prompt = _captured_prompt(create_mock)

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

    create_mock = _make_fake_subprocess()

    provider = ShaiAIProvider()
    with patch.object(ai_providers.asyncio, "create_subprocess_exec", create_mock):
        # Must not raise because of the missing file (Req 3.4).
        result = asyncio.run(
            provider.query("Comment sauvegarder ?", context="donnees critiques")
        )

    prompt = _captured_prompt(create_mock)

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

    create_mock = _make_fake_subprocess()

    provider = ShaiAIProvider()
    with patch.object(ai_providers.asyncio, "create_subprocess_exec", create_mock):
        result = asyncio.run(provider.query("Une simple question ?"))

    prompt = _captured_prompt(create_mock)

    assert prompt == "Question: Une simple question ?"
    assert "Contexte:" not in prompt
    assert result["provider"] == "shai"

"""Tests for the Shai skill-context loader.

Feature: shai-ia-context

Covers optional test task:
- 2.3  Unit tests for `_load_shai_skill_context()`

The loader reads `SHAI_SKILL_CONTEXT_PATH` and returns the stripped content on
success, or `None` on any failure (missing/empty/unreadable), logging a warning
on the filesystem-error paths and never raising because of the file.

Requirements: 2.1, 3.1, 3.2, 3.3, 3.4
"""
import os

import pytest

import app.oracle.ai_providers as ai_providers
from app.oracle.ai_providers import _load_shai_skill_context


# ---------------------------------------------------------------------------
# Success path (Req 2.1)
# ---------------------------------------------------------------------------

def test_load_returns_stripped_content_on_success(tmp_path, monkeypatch):
    """A readable, non-empty file yields its stripped content."""
    ctx_file = tmp_path / "shai_context.md"
    ctx_file.write_text("  Contexte metier OPCP.\n\n", encoding="utf-8")
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(ctx_file))

    result = _load_shai_skill_context()

    assert result == "Contexte metier OPCP."


def test_load_preserves_inner_content_only_strips_edges(tmp_path, monkeypatch):
    """Only leading/trailing whitespace is stripped; inner content is kept."""
    ctx_file = tmp_path / "shai_context.md"
    ctx_file.write_text("\n# Titre\n\nLigne 1\nLigne 2\n", encoding="utf-8")
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(ctx_file))

    result = _load_shai_skill_context()

    assert result == "# Titre\n\nLigne 1\nLigne 2"


# ---------------------------------------------------------------------------
# Empty / whitespace-only file -> None, no warning (Req 3.x edge)
# ---------------------------------------------------------------------------

def test_load_returns_none_for_empty_file(tmp_path, monkeypatch):
    """An empty file is treated as no skill context (None), without warning."""
    ctx_file = tmp_path / "shai_context.md"
    ctx_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(ctx_file))

    warning = _capture_warning(monkeypatch)

    result = _load_shai_skill_context()

    assert result is None
    # Empty file is a valid (readable) file, so no filesystem warning is emitted.
    assert warning.calls == []


def test_load_returns_none_for_whitespace_only_file(tmp_path, monkeypatch):
    """A whitespace-only file strips down to empty and is treated as None."""
    ctx_file = tmp_path / "shai_context.md"
    ctx_file.write_text("   \n\t\n  ", encoding="utf-8")
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(ctx_file))

    result = _load_shai_skill_context()

    assert result is None


# ---------------------------------------------------------------------------
# Missing file -> None + warning, no exception (Req 3.1, 3.3, 3.4)
# ---------------------------------------------------------------------------

def test_load_returns_none_and_warns_when_file_missing(tmp_path, monkeypatch):
    """A missing file returns None, logs a warning, and does not raise."""
    missing = tmp_path / "does_not_exist.md"
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(missing))

    warning = _capture_warning(monkeypatch)

    result = _load_shai_skill_context()  # must not raise

    assert result is None
    assert len(warning.calls) == 1
    assert str(missing) in warning.calls[0]


# ---------------------------------------------------------------------------
# Directory / unreadable -> None + warning, no exception (Req 3.2, 3.3, 3.4)
# ---------------------------------------------------------------------------

def test_load_returns_none_and_warns_when_path_is_directory(tmp_path, monkeypatch):
    """A path pointing at a directory raises IsADirectoryError internally,
    which is caught: returns None, logs a warning, does not propagate."""
    a_dir = tmp_path / "context_dir"
    a_dir.mkdir()
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(a_dir))

    warning = _capture_warning(monkeypatch)

    result = _load_shai_skill_context()  # must not raise

    assert result is None
    assert len(warning.calls) == 1
    assert str(a_dir) in warning.calls[0]


@pytest.mark.skipif(
    os.geteuid() == 0 if hasattr(os, "geteuid") else False,
    reason="Root bypasses file permission checks, so an unreadable file is still readable.",
)
def test_load_returns_none_and_warns_when_file_unreadable(tmp_path, monkeypatch):
    """A file without read permission raises PermissionError internally,
    which is caught: returns None, logs a warning, does not propagate."""
    ctx_file = tmp_path / "shai_context.md"
    ctx_file.write_text("secret domain context", encoding="utf-8")
    os.chmod(ctx_file, 0o000)
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(ctx_file))

    warning = _capture_warning(monkeypatch)

    try:
        result = _load_shai_skill_context()  # must not raise
    finally:
        # Restore perms so tmp_path cleanup can remove the file.
        os.chmod(ctx_file, 0o644)

    assert result is None
    assert len(warning.calls) == 1
    assert str(ctx_file) in warning.calls[0]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

class _WarningRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, message, *args, **kwargs):
        self.calls.append(str(message))


def _capture_warning(monkeypatch):
    """Replace logger.warning on the module logger with a recorder."""
    recorder = _WarningRecorder()
    monkeypatch.setattr(ai_providers.logger, "warning", recorder)
    return recorder

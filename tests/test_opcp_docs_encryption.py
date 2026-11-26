"""Encrypted OPCP reference documentation (docs/opcp_external_docs).

Covers the crypto primitives, in-place decryption with the configured key,
the "no key" fallback (notice added to the Shai prompt) and the fact that the
repository copy is stored encrypted.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings as hsettings, strategies as st

import app.oracle.ai_providers as ai_providers
from app.config import settings
from app.oracle import opcp_docs
from app.oracle.opcp_docs import (
    ENCRYPTED_DOCS_NOTICE,
    KEY_PLACEHOLDER,
    decrypt_opcp_docs,
    encrypted_docs_notice,
    ensure_opcp_docs_decrypted,
    get_decryption_key,
    has_encrypted_docs,
    iter_doc_files,
)
from app.security.opcp_docs_crypto import (
    InvalidToken,
    decrypt_bytes,
    encrypt_bytes,
    is_encrypted,
    new_salt,
)

KEY = "unit-test-passphrase"
SALT = new_salt()


@pytest.fixture
def docs_dir(tmp_path, monkeypatch):
    """A temporary docs folder (with a subfolder) wired in as OPCP_DOCS_DIR."""
    root = tmp_path / "opcp_external_docs"
    (root / "sub").mkdir(parents=True)
    (root / "a.md").write_bytes(encrypt_bytes("# A\nalpha é\n".encode(), KEY, SALT))
    (root / "sub" / "b.md").write_bytes(encrypt_bytes(b"# B\nbeta\n", KEY, SALT))
    (root / "plain.md").write_bytes(b"# Already plain\n")
    monkeypatch.setattr(opcp_docs, "OPCP_DOCS_DIR", str(root))
    return root


def _set_key(monkeypatch, value):
    monkeypatch.setattr(settings, "KEY_DECRYPT_INFORMATIONS_OPCP", value)


# --- primitives -------------------------------------------------------------

@pytest.mark.property
@hsettings(max_examples=25, deadline=None)
@given(st.binary(max_size=2000))
def test_encrypt_decrypt_roundtrip(data):
    blob = encrypt_bytes(data, KEY, SALT)
    assert is_encrypted(blob)
    assert decrypt_bytes(blob, KEY) == data


def test_wrong_key_is_rejected():
    blob = encrypt_bytes(b"secret", KEY, SALT)
    with pytest.raises(InvalidToken):
        decrypt_bytes(blob, "wrong-key")


def test_plaintext_is_not_detected_as_encrypted():
    assert not is_encrypted(b"# Title\n")
    with pytest.raises(ValueError):
        decrypt_bytes(b"# Title\n", KEY)


# --- key handling -----------------------------------------------------------

@pytest.mark.parametrize("value", ["", "   ", KEY_PLACEHOLDER])
def test_empty_or_placeholder_key_means_no_key(monkeypatch, value):
    _set_key(monkeypatch, value)
    assert get_decryption_key() is None


# --- in-place decryption ----------------------------------------------------

def test_decrypts_all_files_recursively_in_place(docs_dir, monkeypatch):
    _set_key(monkeypatch, KEY)
    assert ensure_opcp_docs_decrypted() is True
    assert (docs_dir / "a.md").read_text(encoding="utf-8") == "# A\nalpha é\n"
    assert (docs_dir / "sub" / "b.md").read_bytes() == b"# B\nbeta\n"
    assert (docs_dir / "plain.md").read_bytes() == b"# Already plain\n"
    assert not has_encrypted_docs()
    assert not any(p.name.endswith(".tmp-decrypt") for p in iter_doc_files())


def test_already_decrypted_files_are_left_untouched(docs_dir, monkeypatch):
    _set_key(monkeypatch, KEY)
    first = decrypt_opcp_docs()
    assert len(first.decrypted) == 2
    second = decrypt_opcp_docs()
    assert second.decrypted == [] and second.failed == []
    assert len(second.already_plain) == 3


def test_without_key_files_stay_encrypted(docs_dir, monkeypatch):
    _set_key(monkeypatch, KEY_PLACEHOLDER)
    assert ensure_opcp_docs_decrypted() is False
    assert is_encrypted((docs_dir / "a.md").read_bytes())


def test_wrong_key_leaves_files_encrypted(docs_dir, monkeypatch):
    _set_key(monkeypatch, "wrong-key")
    assert ensure_opcp_docs_decrypted() is False
    assert is_encrypted((docs_dir / "a.md").read_bytes())
    assert is_encrypted((docs_dir / "sub" / "b.md").read_bytes())


# --- Shai notice ------------------------------------------------------------

def test_notice_when_encrypted_and_no_key(docs_dir, monkeypatch):
    _set_key(monkeypatch, "")
    assert encrypted_docs_notice() == ENCRYPTED_DOCS_NOTICE


def test_no_notice_when_key_present(docs_dir, monkeypatch):
    _set_key(monkeypatch, KEY)
    assert encrypted_docs_notice() is None
    assert not has_encrypted_docs()


def test_no_notice_when_docs_plaintext(tmp_path, monkeypatch):
    (tmp_path / "x.md").write_text("plain")
    monkeypatch.setattr(opcp_docs, "OPCP_DOCS_DIR", str(tmp_path))
    _set_key(monkeypatch, "")
    assert encrypted_docs_notice() is None


def test_shai_prompt_includes_notice_without_key(docs_dir, monkeypatch, tmp_path):
    _set_key(monkeypatch, "")
    skill = tmp_path / "shai_context.md"
    skill.write_text("SKILL", encoding="utf-8")
    monkeypatch.setattr(ai_providers, "SHAI_SKILL_CONTEXT_PATH", str(skill))
    monkeypatch.setattr(settings, "SHAI_API_KEY", "test-key")

    create = MagicMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        usage=SimpleNamespace(total_tokens=1),
    ))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    provider = ai_providers.ShaiAIProvider()
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    asyncio.run(provider.query("Q?"))
    prompt = create.call_args.kwargs["messages"][0]["content"]
    assert prompt == f"SKILL\n\n{ENCRYPTED_DOCS_NOTICE}\n\nQuestion: Q?"


def test_build_prompt_is_unchanged_without_notice():
    assert ai_providers._build_shai_prompt("S", "C", "Q") == "S\n\nContexte: C\n\nQuestion: Q"


# --- repository state -------------------------------------------------------

def test_repository_docs_are_stored_encrypted():
    """Every committed file under docs/opcp_external_docs must be encrypted."""
    root = opcp_docs.resolve_docs_dir()
    files = iter_doc_files(root)
    assert files, "docs/opcp_external_docs is empty"
    plain = [str(p.relative_to(root)) for p in files if not is_encrypted(p.read_bytes())]
    assert plain == [], f"Plaintext files found (run scripts/opcp_docs_crypto.py encrypt): {plain}"

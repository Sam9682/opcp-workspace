#!/usr/bin/env python3
"""Encrypt, decrypt or inspect the OPCP reference documentation.

Operates on every file under ``docs/opcp_external_docs`` (recursively), in
place. The passphrase is read from ``KEY_DECRYPT_INFORMATIONS_OPCP`` or prompted
for; it is never written anywhere.

Usage (from the repository root)::

    python scripts/opcp_docs_crypto.py status
    python scripts/opcp_docs_crypto.py encrypt     # before committing docs changes
    python scripts/opcp_docs_crypto.py decrypt     # to edit the docs locally

Already-encrypted files are skipped by ``encrypt`` and already-decrypted files
by ``decrypt``. Re-encrypt before committing: the repository must only contain
encrypted copies.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.security.opcp_docs_crypto import (  # noqa: E402  (settings-free module)
    InvalidToken,
    decrypt_bytes,
    encrypt_bytes,
    is_encrypted,
    new_salt,
)

DEFAULT_DIR = REPO_ROOT / "docs" / "opcp_external_docs"
ENV_VAR = "KEY_DECRYPT_INFORMATIONS_OPCP"
PLACEHOLDER = "!!!ENTER_THE_KEY_HERE"


def _files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def _passphrase(confirm: bool) -> str:
    key = os.environ.get(ENV_VAR, "").strip()
    if key and key != PLACEHOLDER:
        return key
    key = getpass.getpass(f"{ENV_VAR}: ")
    if confirm and getpass.getpass("Confirm: ") != key:
        sys.exit("Passphrases do not match")
    if not key:
        sys.exit("A passphrase is required")
    return key


def _write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp-crypt")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def cmd_status(root: Path) -> int:
    files = _files(root)
    enc = [p for p in files if is_encrypted(p.read_bytes())]
    print(f"{len(enc)} encrypted / {len(files) - len(enc)} plaintext file(s) in {root}")
    for p in files:
        if p not in enc:
            print(f"  plaintext: {p.relative_to(root)}")
    return 0


def cmd_encrypt(root: Path) -> int:
    key = _passphrase(confirm=True)
    salt = new_salt()  # one salt per run: a single key derivation at decryption time
    done = skipped = 0
    for p in _files(root):
        data = p.read_bytes()
        if is_encrypted(data):
            skipped += 1
            continue
        _write(p, encrypt_bytes(data, key, salt))
        done += 1
    print(f"Encrypted {done} file(s), {skipped} already encrypted")
    return 0


def cmd_decrypt(root: Path) -> int:
    key = _passphrase(confirm=False)
    done = skipped = failed = 0
    for p in _files(root):
        data = p.read_bytes()
        if not is_encrypted(data):
            skipped += 1
            continue
        try:
            _write(p, decrypt_bytes(data, key))
            done += 1
        except (InvalidToken, ValueError):
            failed += 1
            print(f"  cannot decrypt (wrong key?): {p.relative_to(root)}", file=sys.stderr)
    print(f"Decrypted {done} file(s), {skipped} already plaintext, {failed} failed")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["status", "encrypt", "decrypt"])
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="documentation folder")
    args = parser.parse_args()
    if not args.dir.is_dir():
        sys.exit(f"Folder not found: {args.dir}")
    return {"status": cmd_status, "encrypt": cmd_encrypt, "decrypt": cmd_decrypt}[args.command](args.dir)


if __name__ == "__main__":
    sys.exit(main())

"""Access to the encrypted OPCP reference documentation.

``docs/opcp_external_docs`` (and its subfolders) is stored encrypted. When the
application has the passphrase (``KEY_DECRYPT_INFORMATIONS_OPCP``), it decrypts
the files **in place** at startup so the Oracle can use them as plain
Markdown. Files that are already decrypted are left untouched.

When no usable key is configured (empty, or still the ``.env.example``
placeholder), or the key is wrong, the files stay encrypted and the Shai
provider is told not to read them (see :func:`encrypted_docs_notice`).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.config import settings
from app.logging_config import logger
from app.security.opcp_docs_crypto import InvalidToken, decrypt_bytes, is_encrypted, MAGIC

# Folder of the OPCP reference documentation, relative to the project root.
OPCP_DOCS_DIR = "docs/opcp_external_docs"

# Default value shipped in .env.example; treated as "no key configured".
KEY_PLACEHOLDER = "!!!ENTER_THE_KEY_HERE"

# Added to the Shai prompt while the documentation is still encrypted.
ENCRYPTED_DOCS_NOTICE = (
    "Note: the OPCP reference documentation in `./docs/opcp_external_docs` is "
    "encrypted and no decryption key is configured on this server. There is no "
    "need to read the files in `./docs/opcp_external_docs`: their contents are "
    "unreadable. Answer from your own knowledge and say that the OPCP reference "
    "documentation is currently unavailable when it would have been needed."
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class DecryptionReport:
    decrypted: List[Path] = field(default_factory=list)
    already_plain: List[Path] = field(default_factory=list)
    failed: List[Path] = field(default_factory=list)


def resolve_docs_dir(docs_dir: Optional[Path] = None) -> Path:
    path = Path(docs_dir) if docs_dir is not None else Path(OPCP_DOCS_DIR)
    return path if path.is_absolute() else _PROJECT_ROOT / path


def get_decryption_key() -> Optional[str]:
    """The configured passphrase, or None when unset or still the placeholder."""
    key = (settings.KEY_DECRYPT_INFORMATIONS_OPCP or "").strip()
    if not key or key == KEY_PLACEHOLDER:
        return None
    return key


def iter_doc_files(docs_dir: Optional[Path] = None) -> List[Path]:
    root = resolve_docs_dir(docs_dir)
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def _file_is_encrypted(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return is_encrypted(f.read(len(MAGIC)))
    except OSError:
        return False


def has_encrypted_docs(docs_dir: Optional[Path] = None) -> bool:
    """True if at least one documentation file is still encrypted."""
    return any(_file_is_encrypted(p) for p in iter_doc_files(docs_dir))


def decrypt_opcp_docs(
    passphrase: Optional[str] = None, docs_dir: Optional[Path] = None
) -> DecryptionReport:
    """Decrypt every encrypted file under the docs folder, in place.

    Uses the configured key when ``passphrase`` is None. Already-decrypted
    files are skipped. A file that cannot be decrypted (wrong key, corrupted,
    read-only filesystem) is left as is and reported in ``failed``.
    """
    report = DecryptionReport()
    key = passphrase if passphrase is not None else get_decryption_key()
    for path in iter_doc_files(docs_dir):
        try:
            data = path.read_bytes()
        except OSError:
            report.failed.append(path)
            continue
        if not is_encrypted(data):
            report.already_plain.append(path)
            continue
        if not key:
            report.failed.append(path)
            continue
        try:
            plaintext = decrypt_bytes(data, key)
            tmp = path.with_name(path.name + ".tmp-decrypt")
            tmp.write_bytes(plaintext)
            os.replace(tmp, path)
            report.decrypted.append(path)
        except (InvalidToken, ValueError, OSError):
            report.failed.append(path)
    return report


def ensure_opcp_docs_decrypted() -> bool:
    """Startup hook: decrypt the docs if a key is available.

    Returns True when no encrypted file remains. Never raises.
    """
    try:
        files = iter_doc_files()
        if not files:
            return True
        if not any(_file_is_encrypted(p) for p in files):
            logger.info("OPCP reference documentation is already decrypted")
            return True
        if get_decryption_key() is None:
            logger.warning(
                "OPCP reference documentation is encrypted and "
                "KEY_DECRYPT_INFORMATIONS_OPCP is not set: Shai will be told the "
                "documents are unavailable"
            )
            return False
        report = decrypt_opcp_docs()
        if report.failed:
            logger.warning(
                f"OPCP reference documentation: {len(report.decrypted)} file(s) "
                f"decrypted, {len(report.failed)} file(s) could not be decrypted "
                "(wrong KEY_DECRYPT_INFORMATIONS_OPCP or read-only folder?)"
            )
            return False
        logger.info(
            f"OPCP reference documentation decrypted ({len(report.decrypted)} file(s))"
        )
        return True
    except Exception as exc:  # pragma: no cover - defensive; never block startup
        logger.warning(f"Could not decrypt the OPCP reference documentation: {exc}")
        return False


def encrypted_docs_notice() -> Optional[str]:
    """Notice for the Shai prompt while the docs are encrypted, else None.

    Retries decryption first, so a key added later (or files restored
    encrypted) is handled without a restart.
    """
    if not has_encrypted_docs():
        return None
    if get_decryption_key() is not None and ensure_opcp_docs_decrypted():
        return None
    return ENCRYPTED_DOCS_NOTICE

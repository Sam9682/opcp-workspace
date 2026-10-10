#!/usr/bin/env python3
"""Offline migration for application-level database field encryption.

Encrypts (when enabling) or decrypts (when disabling) the in-scope free-text
columns, then flips ``encryption_config.enabled`` to the target state. The flag
is flipped ONLY after every in-scope row has been migrated, so the stored flag
and the on-disk data stay consistent.

In-scope columns (non-indexed free text):
    forum_topics.title
    forum_posts.content
    users.first_name
    users.last_name
    notifications.content
    events.description
    tasks.description

Key handling:
- The administrator's password key is read from the ``DB_ENCRYPTION_PASSWORD``
  environment variable, or prompted for interactively (never passed on argv so
  it does not leak into shell history / process listings).
- The key is validated against the stored salted verification hash before any
  data is touched. A wrong key aborts with a non-zero exit and no changes.

Idempotency:
- Each row is inspected: already-encrypted values (Fernet prefix) are skipped
  when encrypting; plaintext values are skipped when decrypting. Re-running the
  script is safe.

Usage:
    # Enable encryption (encrypt all in-scope plaintext, then flip flag on):
    python scripts/migrate_encryption.py --enable

    # Disable encryption (decrypt all in-scope ciphertext, then flip flag off):
    python scripts/migrate_encryption.py --disable

    # Non-interactive (CI / automation):
    DB_ENCRYPTION_PASSWORD=... python scripts/migrate_encryption.py --enable

Exit codes:
    0  success
    1  usage / configuration error
    2  wrong password key (no changes made)
    3  migration failure (flag NOT flipped)
"""
import argparse
import getpass
import os
import sys
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

# Allow running as a standalone script (``python scripts/migrate_encryption.py``)
# by ensuring the repository root is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.security import encryption  # noqa: E402
from app.security import config_service  # noqa: E402


# (table, primary-key column, target column)
IN_SCOPE_COLUMNS = [
    ("forum_topics", "id", "title"),
    ("forum_posts", "id", "content"),
    ("users", "id", "first_name"),
    ("users", "id", "last_name"),
    ("notifications", "id", "content"),
    ("events", "id", "description"),
    ("tasks", "id", "description"),
]

_FERNET_PREFIX = "gAAAAA"


def _looks_encrypted(value: str) -> bool:
    return value.startswith(_FERNET_PREFIX)


@dataclass
class ColumnResult:
    table: str
    column: str
    changed: int
    skipped: int


def _migrate_column(
    db: Session,
    key: bytes,
    table: str,
    pk: str,
    column: str,
    enable: bool,
    batch_size: int,
) -> ColumnResult:
    """Encrypt or decrypt one column for every row, in batches."""
    changed = 0
    skipped = 0

    rows = db.execute(
        text(f"SELECT {pk} AS pk, {column} AS val FROM {table}")
    ).mappings().all()

    pending = []
    for row in rows:
        value = row["val"]
        if value is None:
            skipped += 1
            continue
        if enable:
            if _looks_encrypted(value):
                skipped += 1
                continue
            new_value = encryption.encrypt(value, key)
        else:
            if not _looks_encrypted(value):
                skipped += 1
                continue
            try:
                new_value = encryption.decrypt(value, key)
            except encryption.InvalidToken:
                # Value is not decryptable with this key; leave untouched.
                skipped += 1
                continue
        pending.append({"pk": row["pk"], "val": new_value})

        if len(pending) >= batch_size:
            _apply_batch(db, table, pk, column, pending)
            changed += len(pending)
            pending = []

    if pending:
        _apply_batch(db, table, pk, column, pending)
        changed += len(pending)

    return ColumnResult(table=table, column=column, changed=changed, skipped=skipped)


def _apply_batch(db: Session, table: str, pk: str, column: str, batch: list) -> None:
    stmt = text(f"UPDATE {table} SET {column} = :val WHERE {pk} = :pk")
    for item in batch:
        db.execute(stmt, {"val": item["val"], "pk": item["pk"]})
    db.flush()


def run_migration(
    db: Session,
    password_key: str,
    enable: bool,
    batch_size: int = 500,
) -> list[ColumnResult]:
    """Validate the key, migrate all in-scope columns, then flip the flag.

    Raises ``PermissionError`` if the key does not match the stored hash and a
    key has been set. If no key has been set yet, the supplied key is stored
    first (first-time enable). Returns per-column results.

    All data changes plus the flag flip commit atomically at the end; any
    exception rolls the transaction back so the flag is never flipped on a
    partial migration.
    """
    # Ensure a key/verification hash exists. For a first-time enable, store the
    # supplied key's verification material now.
    if not config_service.key_is_set(db):
        if not enable:
            # Nothing is encrypted yet; disabling is a no-op flag flip.
            config_service.set_verification(db, password_key)
        else:
            config_service.set_verification(db, password_key)

    if not config_service.verify_password_key(db, password_key):
        raise PermissionError("Password key does not match the stored verification hash")

    key = config_service.derive_fernet_key(db, password_key)

    results = []
    try:
        for table, pk, column in IN_SCOPE_COLUMNS:
            results.append(
                _migrate_column(db, key, table, pk, column, enable, batch_size)
            )
        # Flip the flag within the same transaction as the data changes.
        config_service.set_enabled(db, enable)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return results


def _read_password_key() -> str:
    env_key = os.environ.get("DB_ENCRYPTION_PASSWORD", "").strip()
    if env_key:
        return env_key
    return getpass.getpass("Encryption password key: ")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Encrypt/decrypt in-scope DB columns and flip the encryption flag."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--enable", action="store_true", help="Encrypt data and enable encryption")
    group.add_argument("--disable", action="store_true", help="Decrypt data and disable encryption")
    parser.add_argument(
        "--batch-size", type=int, default=500,
        help="Rows per UPDATE batch (default: 500)",
    )
    args = parser.parse_args()

    enable = bool(args.enable)
    action = "ENABLE (encrypt)" if enable else "DISABLE (decrypt)"

    print(f"Database field encryption migration: {action}")
    if enable:
        print(
            "WARNING: once enabled, the password key is the ONLY way to read the\n"
            "         encrypted data. If the key is lost, the data is permanently\n"
            "         unrecoverable.\n"
        )

    password_key = _read_password_key()
    if not password_key or len(password_key) < 8:
        print("ERROR: password key must be at least 8 characters.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        results = run_migration(db, password_key, enable, batch_size=args.batch_size)
    except PermissionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001  - surface and abort without flipping
        print(f"ERROR: migration failed, flag NOT changed: {exc}", file=sys.stderr)
        return 3
    finally:
        db.close()

    print("\nMigration summary:")
    total_changed = 0
    for r in results:
        total_changed += r.changed
        print(f"  {r.table}.{r.column}: {r.changed} changed, {r.skipped} skipped")
    print(f"\nTotal rows migrated: {total_changed}")
    print(f"encryption_config.enabled is now: {enable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Migration smoke test for the account-security 2FA fields revision.

Spec: .kiro/specs/account-security
Task 1.4 — Write a migration smoke test.

Revision under test:
    migrations/versions/20260222_0000_add_account_security_2fa_fields_*.py
    revision       = 'add_account_security_2fa_fields'
    down_revision  = 'per_user_prerequisite_answers'

This is a SMOKE test that drives the real Alembic upgrade/downgrade against a
live database engine and asserts the observable schema outcomes required by the
acceptance criteria:

  * Upgrade adds ``totp_secret``, ``totp_enabled`` and ``email_2fa_enabled`` to
    the ``users`` table; booleans are NOT NULL with a ``false`` server default
    so existing rows backfill safely.                          (Req 5.6, 6.2)
  * Downgrade removes all three columns cleanly.               (Req 5.6, 6.2)
  * A full upgrade -> downgrade cycle runs without error.      (Req 5.6, 6.2)

Validates: Requirements 5.6, 6.2

Engine choice
-------------
The project's migrations are PostgreSQL-only: earlier revisions in the chain use
server-side defaults such as ``gen_random_uuid()`` and named ADD/DROP
CONSTRAINT operations that SQLite cannot execute outside Alembic batch mode.
This test therefore runs against PostgreSQL — the same engine the application
and Alembic use in every real environment.

The database URL is resolved from ``TEST_DATABASE_URL`` (preferred) or the
application's configured ``DATABASE_URL``. If no PostgreSQL server is reachable
(e.g. a developer box without the compose stack up), the whole module is
skipped rather than failing, so CI — where PostgreSQL is available — exercises
it while local runs without a DB stay green.
"""
import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from alembic.config import Config
from alembic import command


USERS_TABLE = "users"

# Revisions that bracket the change under test.
BEFORE_REVISION = "per_user_prerequisite_answers"
UNDER_TEST_REVISION = "add_account_security_2fa_fields"

# Columns the migration adds/removes.
NEW_COLUMNS = ("totp_secret", "totp_enabled", "email_2fa_enabled")
BOOLEAN_COLUMNS = ("totp_enabled", "email_2fa_enabled")


# ---------------------------------------------------------------------------
# Engine resolution + skip-when-unavailable
# ---------------------------------------------------------------------------
def _resolve_db_url() -> str:
    """Prefer an explicit test URL, else fall back to the app's DATABASE_URL."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    try:
        from app.config import settings

        return settings.DATABASE_URL
    except Exception:  # pragma: no cover - config import failure
        return ""


def _make_engine_or_skip() -> Engine:
    url = _resolve_db_url()
    if not url or not url.startswith("postgres"):
        pytest.skip(
            "PostgreSQL migration tests require a Postgres URL "
            "(set TEST_DATABASE_URL or DATABASE_URL); this migration is "
            "Postgres-only and cannot run on SQLite."
        )
    engine = create_engine(url, poolclass=None)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"No reachable PostgreSQL server for migration tests: {exc}")
    return engine


def _alembic_config(url: str) -> Config:
    # alembic.ini lives at the repo root; tests may run from anywhere.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(repo_root, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(repo_root, "migrations"))
    # Alembic stores options in a configparser, which applies %-interpolation.
    # Unix-socket URLs (e.g. ...?host=%2Ftmp%2F...) contain literal '%' that must
    # be escaped as '%%' so configparser does not treat them as interpolations.
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


# ---------------------------------------------------------------------------
# Introspection helpers (dialect-agnostic via SQLAlchemy Inspector)
# ---------------------------------------------------------------------------
def _column_names(engine: Engine, table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _column(engine: Engine, table: str, name: str):
    for c in inspect(engine).get_columns(table):
        if c["name"] == name:
            return c
    return None


# ---------------------------------------------------------------------------
# Fixture: land the DB at BEFORE_REVISION, guarantee cleanup.
# ---------------------------------------------------------------------------
@pytest.fixture()
def migrated_db():
    """Yield (engine, cfg) with schema at ``per_user_prerequisite_answers``.

    The fixture upgrades to the pre-change revision and, on teardown, downgrades
    everything to base so the database is left clean regardless of what the test
    did in between.
    """
    engine = _make_engine_or_skip()
    cfg = _alembic_config(str(engine.url))

    # Start from a known-clean base, then land exactly on the pre-change schema.
    command.downgrade(cfg, "base")
    command.upgrade(cfg, BEFORE_REVISION)

    try:
        yield engine, cfg
    finally:
        # Best-effort: return to base so re-runs start clean.
        try:
            command.downgrade(cfg, "base")
        finally:
            engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_upgrade_adds_the_three_2fa_columns(migrated_db):
    """Upgrade installs totp_secret, totp_enabled and email_2fa_enabled.

    Validates: Requirements 5.6, 6.2
    """
    engine, cfg = migrated_db

    # Pre-condition: none of the 2FA columns exist yet.
    before = _column_names(engine, USERS_TABLE)
    for col in NEW_COLUMNS:
        assert col not in before, f"{col} must not exist before upgrade"

    command.upgrade(cfg, UNDER_TEST_REVISION)

    # Req 5.6 / 6.2: all three columns are present after upgrade.
    after = _column_names(engine, USERS_TABLE)
    for col in NEW_COLUMNS:
        assert col in after, f"{col} must be added on upgrade"

    # totp_secret is nullable (holds a pending secret before confirmation).
    totp_secret = _column(engine, USERS_TABLE, "totp_secret")
    assert totp_secret is not None
    assert totp_secret["nullable"] is True, "totp_secret must be nullable"

    # Boolean flags are NOT NULL so every row has a defined 2FA state.
    for col in BOOLEAN_COLUMNS:
        column = _column(engine, USERS_TABLE, col)
        assert column is not None
        assert column["nullable"] is False, f"{col} must be NOT NULL"


def test_upgrade_backfills_existing_rows_with_false_defaults(migrated_db):
    """The boolean server default lets existing rows backfill safely.

    A user inserted before the upgrade must, after the upgrade, have both
    boolean flags default to false and a null pending secret.
    Validates: Requirements 5.6, 6.2
    """
    engine, cfg = migrated_db

    # Insert a legacy user while the 2FA columns do not yet exist.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, first_name, "
                "last_name, role, is_email_verified, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :email, 'h', 'F', 'L', 'MEMBER', "
                "true, now(), now())"
            ),
            {"email": "legacy@example.com"},
        )

    command.upgrade(cfg, UNDER_TEST_REVISION)

    # The pre-existing row is backfilled with safe defaults, not left NULL.
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT totp_secret, totp_enabled, email_2fa_enabled "
                "FROM users WHERE email = :email"
            ),
            {"email": "legacy@example.com"},
        ).one()
    totp_secret, totp_enabled, email_2fa_enabled = row
    assert totp_secret is None, "existing rows must have a null pending secret"
    assert totp_enabled is False, "totp_enabled must backfill to false"
    assert email_2fa_enabled is False, "email_2fa_enabled must backfill to false"


def test_downgrade_removes_the_three_2fa_columns(migrated_db):
    """Downgrade drops all three columns, leaving the users table as before.

    Validates: Requirements 5.6, 6.2
    """
    engine, cfg = migrated_db

    command.upgrade(cfg, UNDER_TEST_REVISION)
    after_upgrade = _column_names(engine, USERS_TABLE)
    for col in NEW_COLUMNS:
        assert col in after_upgrade

    command.downgrade(cfg, BEFORE_REVISION)

    # Req 5.6 / 6.2: every added column is removed on downgrade.
    after_downgrade = _column_names(engine, USERS_TABLE)
    for col in NEW_COLUMNS:
        assert col not in after_downgrade, f"{col} must be removed on downgrade"


def test_upgrade_downgrade_cycle_runs_cleanly(migrated_db):
    """A full upgrade -> downgrade -> upgrade cycle completes without error and
    lands on a consistent schema each time.

    Validates: Requirements 5.6, 6.2
    """
    engine, cfg = migrated_db

    # First upgrade: columns present.
    command.upgrade(cfg, UNDER_TEST_REVISION)
    assert set(NEW_COLUMNS).issubset(_column_names(engine, USERS_TABLE))

    # Downgrade: columns gone.
    command.downgrade(cfg, BEFORE_REVISION)
    assert not (set(NEW_COLUMNS) & _column_names(engine, USERS_TABLE))

    # Re-upgrade: columns come back (proves the migration is repeatable).
    command.upgrade(cfg, UNDER_TEST_REVISION)
    assert set(NEW_COLUMNS).issubset(_column_names(engine, USERS_TABLE))

"""Migration smoke test for the OpenStack CA-certificate column revision.

Spec: .kiro/specs/openstack-ca-certificate
Task 1.3 — Write a migration smoke test.

Revision under test:
    migrations/versions/20260929_0000_add_credential_ca_certificate_*.py
    revision       = 'add_credential_ca_certificate'
    down_revision  = 'remap_document_categories'

This is a SMOKE test that drives the real Alembic upgrade/downgrade against a
live database engine and asserts the observable schema outcomes required by the
acceptance criteria:

  * Upgrade adds a nullable ``ca_certificate`` column to the
    ``prerequisite_credential_config`` table.                  (Req 2.1, 2.5)
  * Downgrade removes the column cleanly.                      (Req 2.1, 2.5)
  * A full upgrade -> downgrade -> upgrade cycle runs without error.
                                                               (Req 2.1, 2.5)

Validates: Requirements 2.1, 2.5

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


CREDENTIAL_CONFIG_TABLE = "prerequisite_credential_config"

# Revisions that bracket the change under test.
BEFORE_REVISION = "remap_document_categories"
UNDER_TEST_REVISION = "add_credential_ca_certificate"

# Column the migration adds/removes.
NEW_COLUMN = "ca_certificate"


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
    """Yield (engine, cfg) with schema at ``remap_document_categories``.

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
def test_upgrade_adds_nullable_ca_certificate_column(migrated_db):
    """Upgrade installs a nullable ``ca_certificate`` column.

    Validates: Requirements 2.1, 2.5
    """
    engine, cfg = migrated_db

    # Pre-condition: the column does not exist yet, but its table does.
    before = _column_names(engine, CREDENTIAL_CONFIG_TABLE)
    assert NEW_COLUMN not in before, f"{NEW_COLUMN} must not exist before upgrade"

    command.upgrade(cfg, UNDER_TEST_REVISION)

    # Req 2.1: the column is present after upgrade.
    after = _column_names(engine, CREDENTIAL_CONFIG_TABLE)
    assert NEW_COLUMN in after, f"{NEW_COLUMN} must be added on upgrade"

    # Req 2.5: the column is nullable (NULL/empty => system trust store).
    column = _column(engine, CREDENTIAL_CONFIG_TABLE, NEW_COLUMN)
    assert column is not None
    assert column["nullable"] is True, f"{NEW_COLUMN} must be nullable"


def test_upgrade_leaves_existing_rows_with_null_ca_certificate(migrated_db):
    """A config row inserted before the upgrade keeps a NULL CA certificate.

    The column is added nullable with no server default, so pre-existing rows
    have ``ca_certificate = NULL`` after the upgrade (the model normalizes NULL
    to "" on read).
    Validates: Requirements 2.1, 2.5
    """
    engine, cfg = migrated_db

    # A credential config row needs an owning installation (FK). Seed a minimal
    # installation, then a config row, while the CA column does not yet exist.
    with engine.begin() as conn:
        installation_id = conn.execute(
            text(
                "INSERT INTO installations (id, project_name, created_at, "
                "updated_at) VALUES (gen_random_uuid(), :name, now(), now()) "
                "RETURNING id"
            ),
            {"name": "smoke-test-install"},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO prerequisite_credential_config "
                "(id, installation_id, auth_url, credential_id, nova_endpoint, "
                "updated_at) VALUES (gen_random_uuid(), :iid, '', '', '', now())"
            ),
            {"iid": installation_id},
        )

    command.upgrade(cfg, UNDER_TEST_REVISION)

    with engine.connect() as conn:
        ca = conn.execute(
            text(
                "SELECT ca_certificate FROM prerequisite_credential_config "
                "WHERE installation_id = :iid"
            ),
            {"iid": installation_id},
        ).scalar_one()
    assert ca is None, "existing rows must have a NULL ca_certificate after upgrade"


def test_downgrade_removes_ca_certificate_column(migrated_db):
    """Downgrade drops the column, leaving the table as before.

    Validates: Requirements 2.1, 2.5
    """
    engine, cfg = migrated_db

    command.upgrade(cfg, UNDER_TEST_REVISION)
    assert NEW_COLUMN in _column_names(engine, CREDENTIAL_CONFIG_TABLE)

    command.downgrade(cfg, BEFORE_REVISION)

    # Req 2.1 / 2.5: the added column is removed on downgrade.
    after_downgrade = _column_names(engine, CREDENTIAL_CONFIG_TABLE)
    assert NEW_COLUMN not in after_downgrade, (
        f"{NEW_COLUMN} must be removed on downgrade"
    )


def test_upgrade_downgrade_cycle_runs_cleanly(migrated_db):
    """A full upgrade -> downgrade -> upgrade cycle completes without error and
    lands on a consistent schema each time.

    Validates: Requirements 2.1, 2.5
    """
    engine, cfg = migrated_db

    # First upgrade: column present.
    command.upgrade(cfg, UNDER_TEST_REVISION)
    assert NEW_COLUMN in _column_names(engine, CREDENTIAL_CONFIG_TABLE)

    # Downgrade: column gone.
    command.downgrade(cfg, BEFORE_REVISION)
    assert NEW_COLUMN not in _column_names(engine, CREDENTIAL_CONFIG_TABLE)

    # Re-upgrade: column comes back (proves the migration is repeatable).
    command.upgrade(cfg, UNDER_TEST_REVISION)
    assert NEW_COLUMN in _column_names(engine, CREDENTIAL_CONFIG_TABLE)

"""Migration example tests for the per-user prerequisites answers revision.

Spec: .kiro/specs/per-user-prerequisites-persistence
Task 5.2 — Write migration example tests.

Revision under test:
    migrations/versions/20260221_0000_per_user_prerequisite_answers_*.py
    revision       = 'per_user_prerequisite_answers'
    down_revision  = 'create_prerequisites_tables'

These are EXAMPLE (not property) tests. They drive the real Alembic
upgrade/downgrade against a live database engine and assert the observable
schema/data outcomes required by the acceptance criteria:

  * Upgrade empties any pre-existing shared rows and yields a non-null
    ``user_id`` with ``UNIQUE(user_id, slug, row_id)``.        (Req 6.1, 6.2)
  * Downgrade restores ``UNIQUE(slug, row_id)`` and removes the ``user_id``
    column.                                                    (Req 6.3)
  * ``prerequisite_content`` keeps its slug-only primary key and its shared
    value through the whole migrate/rollback cycle.            (Req 4.2)

Validates: Requirements 6.1, 6.2, 6.3, 4.2

Engine choice
-------------
The project's migrations are PostgreSQL-only: they use server-side defaults
such as ``gen_random_uuid()`` and named ADD/DROP CONSTRAINT operations that
SQLite cannot execute outside Alembic batch mode. (Running the migration chain
against SQLite fails on the very first ``create_users_table`` revision.) These
tests therefore run against PostgreSQL — the same engine the application and
Alembic use in every real environment.

The database URL is resolved from ``TEST_DATABASE_URL`` (preferred) or the
application's configured ``DATABASE_URL``. If no PostgreSQL server is reachable
(e.g. a developer box without the compose stack up), the whole module is
skipped rather than failing, so CI — where PostgreSQL is available — exercises
it while local runs without a DB stay green.
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from alembic.config import Config
from alembic import command


ANSWERS_TABLE = "prerequisite_answers"
CONTENT_TABLE = "prerequisite_content"

# Revisions that bracket the change under test.
BEFORE_REVISION = "create_prerequisites_tables"
UNDER_TEST_REVISION = "per_user_prerequisite_answers"

# Named constraints/columns the migration adds/removes.
PER_USER_UNIQUE = "uq_prerequisite_answers_user_slug_row"
SHARED_UNIQUE = "uq_prerequisite_answers_slug_row"
PER_USER_INDEX = "idx_prerequisite_answers_user_slug"
SHARED_INDEX = "idx_prerequisite_answers_slug"


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

def _unique_constraint_columns(engine: Engine, table: str) -> dict[str, list[str]]:
    """Map unique-constraint name -> ordered column list (includes unique indexes)."""
    insp = inspect(engine)
    result: dict[str, list[str]] = {}
    for uc in insp.get_unique_constraints(table):
        result[uc["name"]] = list(uc["column_names"])
    # Postgres may report a UNIQUE CONSTRAINT as a unique index; capture both.
    for ix in insp.get_indexes(table):
        if ix.get("unique"):
            result.setdefault(ix["name"], list(ix["column_names"]))
    return result

def _index_names(engine: Engine, table: str) -> set[str]:
    return {ix["name"] for ix in inspect(engine).get_indexes(table)}


# ---------------------------------------------------------------------------
# Fixture: land the DB at BEFORE_REVISION with seed data, guarantee cleanup.
# ---------------------------------------------------------------------------
@pytest.fixture()
def migrated_db():
    """Yield (engine, cfg) with schema at ``create_prerequisites_tables``.

    The fixture upgrades to the pre-change revision, seeds a shared answer row
    and a static-content row, and on teardown downgrades everything to base so
    the database is left clean regardless of what the test did in between.
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


def _seed_shared_answer_and_content(engine: Engine) -> str:
    """Insert one legacy (owner-less) answer and one shared content row.

    Returns the shared content value so the test can assert it survives.
    """
    shared_content = "SHARED STATIC VALUE " + uuid.uuid4().hex
    with engine.begin() as conn:
        # Legacy shared answer — no user_id column exists yet at this revision.
        conn.execute(
            text(
                "INSERT INTO prerequisite_answers (slug, row_id, answer, updated_at) "
                "VALUES (:slug, :row_id, :answer, now())"
            ),
            {"slug": "vcf", "row_id": "row-1", "answer": "legacy shared answer"},
        )
        conn.execute(
            text(
                "INSERT INTO prerequisite_content (slug, content, updated_at) "
                "VALUES (:slug, :content, now())"
            ),
            {"slug": "basics", "content": shared_content},
        )
    return shared_content


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_upgrade_empties_shared_rows_and_adds_per_user_key(migrated_db):
    """Upgrade discards legacy shared rows and installs the per-user schema.

    Validates: Requirements 6.1, 6.2
    """
    engine, cfg = migrated_db
    _seed_shared_answer_and_content(engine)

    # Pre-condition: shared schema, one legacy row present.
    assert "user_id" not in _column_names(engine, ANSWERS_TABLE)
    with engine.connect() as conn:
        count_before = conn.execute(
            text(f"SELECT count(*) FROM {ANSWERS_TABLE}")
        ).scalar_one()
    assert count_before == 1

    command.upgrade(cfg, UNDER_TEST_REVISION)

    # Req 6.2: pre-existing shared answer rows are discarded.
    with engine.connect() as conn:
        count_after = conn.execute(
            text(f"SELECT count(*) FROM {ANSWERS_TABLE}")
        ).scalar_one()
    assert count_after == 0, "legacy shared answers should be discarded on upgrade"

    # Req 6.1: a non-null user_id column now exists.
    user_id_col = _column(engine, ANSWERS_TABLE, "user_id")
    assert user_id_col is not None, "user_id column must be added on upgrade"
    assert user_id_col["nullable"] is False, "user_id must be NOT NULL"

    # Req 6.1: uniqueness is keyed on (user_id, slug, row_id).
    uniques = _unique_constraint_columns(engine, ANSWERS_TABLE)
    assert PER_USER_UNIQUE in uniques, (
        f"expected unique constraint {PER_USER_UNIQUE}; found {sorted(uniques)}"
    )
    assert uniques[PER_USER_UNIQUE] == ["user_id", "slug", "row_id"]

    # The old shared unique key must be gone.
    assert SHARED_UNIQUE not in uniques, "shared unique key must not survive upgrade"

    # The per-user composite index is present; the slug-only one is gone.
    idx = _index_names(engine, ANSWERS_TABLE)
    assert PER_USER_INDEX in idx
    assert SHARED_INDEX not in idx


def test_upgrade_enforces_user_slug_row_uniqueness(migrated_db):
    """After upgrade, duplicate (user_id, slug, row_id) is rejected but the same
    (slug, row_id) for a different user is accepted.

    This proves the new key is on the triple, not the old (slug, row_id) pair.
    Validates: Requirements 6.1
    """
    engine, cfg = migrated_db
    command.upgrade(cfg, UNDER_TEST_REVISION)

    # Two real users to satisfy the FK on user_id -> users.id.
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    with engine.begin() as conn:
        for uid, email in ((user_a, "a@example.com"), (user_b, "b@example.com")):
            conn.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, first_name, "
                    "last_name, role, is_email_verified, created_at, updated_at) "
                    "VALUES (:id, :email, 'h', 'F', 'L', 'MEMBER', true, now(), now())"
                ),
                {"id": uid, "email": email},
            )

    def _insert(uid):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO prerequisite_answers (user_id, slug, row_id, answer, updated_at) "
                    "VALUES (:uid, 'vcf', 'row-1', 'ans', now())"
                ),
                {"uid": uid},
            )

    # Same (slug, row_id) for two different users is allowed.
    _insert(user_a)
    _insert(user_b)
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT count(*) FROM {ANSWERS_TABLE}")
        ).scalar_one()
    assert total == 2, "distinct users may share the same (slug, row_id)"

    # A duplicate of the full (user_id, slug, row_id) triple is rejected.
    with pytest.raises(Exception):
        _insert(user_a)


def test_downgrade_restores_shared_key_and_drops_user_id(migrated_db):
    """Downgrade restores UNIQUE(slug, row_id) and removes the user_id column.

    Validates: Requirements 6.3
    """
    engine, cfg = migrated_db

    command.upgrade(cfg, UNDER_TEST_REVISION)
    assert "user_id" in _column_names(engine, ANSWERS_TABLE)

    command.downgrade(cfg, BEFORE_REVISION)

    # Req 6.3: user_id column is gone.
    assert "user_id" not in _column_names(engine, ANSWERS_TABLE), (
        "user_id column must be removed on downgrade"
    )

    # Req 6.3: the shared (slug, row_id) uniqueness is restored; per-user gone.
    uniques = _unique_constraint_columns(engine, ANSWERS_TABLE)
    assert SHARED_UNIQUE in uniques, (
        f"expected restored unique {SHARED_UNIQUE}; found {sorted(uniques)}"
    )
    assert uniques[SHARED_UNIQUE] == ["slug", "row_id"]
    assert PER_USER_UNIQUE not in uniques

    # The slug-only index is restored; the per-user composite index is gone.
    idx = _index_names(engine, ANSWERS_TABLE)
    assert SHARED_INDEX in idx
    assert PER_USER_INDEX not in idx


def test_prerequisite_content_unchanged_across_migration(migrated_db):
    """prerequisite_content keeps its slug-only PK and shared value throughout.

    The migration must not touch prerequisite_content at all: its primary key
    stays ``slug`` and the stored shared value survives both the upgrade and the
    subsequent downgrade.
    Validates: Requirements 4.2
    """
    engine, cfg = migrated_db
    shared_content = _seed_shared_answer_and_content(engine)

    def _content_pk_columns() -> list[str]:
        return list(inspect(engine).get_pk_constraint(CONTENT_TABLE)["constrained_columns"])

    def _stored_content() -> str:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT content FROM prerequisite_content WHERE slug = 'basics'")
            ).scalar_one()

    # Baseline at the pre-change revision.
    assert _content_pk_columns() == ["slug"]
    assert _stored_content() == shared_content

    # After upgrade: content table untouched.
    command.upgrade(cfg, UNDER_TEST_REVISION)
    assert _content_pk_columns() == ["slug"], "content PK must remain slug-only"
    assert "user_id" not in _column_names(engine, CONTENT_TABLE), (
        "content table must not gain a user scope"
    )
    assert _stored_content() == shared_content, "shared content must survive upgrade"

    # After downgrade: still untouched.
    command.downgrade(cfg, BEFORE_REVISION)
    assert _content_pk_columns() == ["slug"]
    assert _stored_content() == shared_content, "shared content must survive downgrade"

"""Tests for the offline encryption migration script (Task 6).

Drives ``scripts.migrate_encryption.run_migration`` against the in-memory
SQLite db_session. Verifies encrypt-then-flag-on, decrypt-then-flag-off,
idempotency, and that a wrong key aborts without changes.
"""
import pytest
from sqlalchemy import text

from app.models import User, UserRole, Topic, Post
from app.security import config_service
from app.security.key_provider import key_provider

from scripts.migrate_encryption import run_migration


@pytest.fixture(autouse=True)
def _clear_key_provider():
    key_provider.clear()
    config_service._invalidate_cache()
    yield
    key_provider.clear()
    config_service._invalidate_cache()


def _seed(db):
    """Seed plaintext author + topic + post; key provider stays inactive so the
    ORM writes plaintext."""
    author = User(
        email="author@example.com",
        password_hash="h",
        first_name="Jean",
        last_name="Dupont",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db.add(author)
    db.commit()
    topic = Topic(title="Plain Title", author_id=author.id)
    db.add(topic)
    db.commit()
    post = Post(topic_id=topic.id, author_id=author.id, content="Plain content")
    db.add(post)
    db.commit()
    return author, topic, post


def _raw(db, table, column, row_id):
    """Raw stored value by primary key, matched in Python (SQLite-safe)."""
    rows = db.execute(text(f"SELECT id AS rid, {column} AS val FROM {table}")).mappings().all()
    target = str(row_id).replace("-", "")
    for row in rows:
        if str(row["rid"]).replace("-", "") == target:
            return row["val"]
    return None


def test_enable_encrypts_and_flips_flag(db_session):
    author, topic, post = _seed(db_session)

    results = run_migration(db_session, "supersecret", enable=True)

    # Flag flipped on.
    assert config_service.get_encryption_enabled(db_session) is True

    # Raw stored values are now ciphertext.
    assert _raw(db_session, "users", "first_name", author.id).startswith("gAAAAA")
    assert _raw(db_session, "forum_topics", "title", topic.id).startswith("gAAAAA")
    assert _raw(db_session, "forum_posts", "content", post.id).startswith("gAAAAA")

    # Some rows were changed.
    assert sum(r.changed for r in results) >= 3


def test_round_trip_enable_then_disable(db_session):
    author, topic, post = _seed(db_session)

    run_migration(db_session, "supersecret", enable=True)
    run_migration(db_session, "supersecret", enable=False)

    # Flag flipped off and values are plaintext again.
    assert config_service.get_encryption_enabled(db_session) is False
    assert _raw(db_session, "users", "first_name", author.id) == "Jean"
    assert _raw(db_session, "forum_topics", "title", topic.id) == "Plain Title"
    assert _raw(db_session, "forum_posts", "content", post.id) == "Plain content"


def test_enable_is_idempotent(db_session):
    _seed(db_session)
    run_migration(db_session, "supersecret", enable=True)
    # Second run should skip already-encrypted rows (no further changes).
    results = run_migration(db_session, "supersecret", enable=True)
    assert sum(r.changed for r in results) == 0


def test_wrong_key_aborts_without_changes(db_session):
    author, topic, post = _seed(db_session)
    # First set the key via an initial (encrypt) run.
    run_migration(db_session, "supersecret", enable=True)

    # A different key must be rejected and must not alter data.
    before = _raw(db_session, "users", "first_name", author.id)
    with pytest.raises(PermissionError):
        run_migration(db_session, "wrong-key-xyz", enable=False)
    after = _raw(db_session, "users", "first_name", author.id)
    assert before == after
    # Flag is still enabled (unchanged).
    assert config_service.get_encryption_enabled(db_session) is True

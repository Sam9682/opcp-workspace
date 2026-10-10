"""End-to-end tests for EncryptedString applied to real models (Task 7).

Verifies that, with an active key, values written through the ORM are stored as
ciphertext at the raw-SQL level while ORM reads return the original plaintext;
and that with no key active, values are stored and read as plaintext.

Uses the in-memory SQLite db_session fixture. Raw stored values are inspected
with a bind-parameter-free text() query so the EncryptedString type does not
re-process them.
"""
import pytest
from sqlalchemy import text

from app.models import User, UserRole, Topic, Post
from app.security import encryption
from app.security.key_provider import key_provider
from app.security import config_service


@pytest.fixture(autouse=True)
def _clear_key_provider():
    key_provider.clear()
    config_service._invalidate_cache()
    yield
    key_provider.clear()
    config_service._invalidate_cache()


def _raw_value(db, table: str, column: str, row_id) -> str:
    """Read a column's raw stored value by primary key.

    Selects both the id and the target column via a textual projection (so the
    ``EncryptedString`` type never re-processes the value), then matches the row
    in Python by comparing the string form of the id. This avoids depending on
    how SQLAlchemy's ``Uuid`` type stores the id under SQLite.
    """
    rows = db.execute(text(f"SELECT id AS rid, {column} AS val FROM {table}")).mappings().all()
    # SQLite stores the UUID as a dash-less 32-char hex string; normalise both
    # sides before comparing.
    target = str(row_id).replace("-", "")
    for row in rows:
        if str(row["rid"]).replace("-", "") == target:
            return row["val"]
    return None


def test_user_name_plaintext_when_key_inactive(db_session):
    user = User(
        email="plain@example.com",
        password_hash="h",
        first_name="Jean",
        last_name="Dupont",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()

    raw = _raw_value(db_session, "users", "first_name", user.id)
    assert raw == "Jean"


def test_user_name_encrypted_when_key_active(db_session):
    key = encryption.derive_key("pw", encryption.generate_salt())
    key_provider.set_key(key)

    user = User(
        email="enc@example.com",
        password_hash="h",
        first_name="Jean",
        last_name="Dupont",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.expire_all()  # force a reload from the DB

    # Raw stored value is ciphertext...
    raw = _raw_value(db_session, "users", "first_name", user.id)
    assert raw != "Jean"
    assert raw.startswith("gAAAAA")

    # ...but the ORM read returns the original plaintext.
    reloaded = db_session.query(User).filter(User.id == user.id).first()
    assert reloaded.first_name == "Jean"
    assert reloaded.last_name == "Dupont"


def test_forum_post_and_topic_encrypted_when_key_active(db_session):
    key = encryption.derive_key("pw", encryption.generate_salt())
    key_provider.set_key(key)

    author = User(
        email="author@example.com",
        password_hash="h",
        first_name="A",
        last_name="B",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(author)
    db_session.commit()

    topic = Topic(title="Secret Topic Title", author_id=author.id)
    db_session.add(topic)
    db_session.commit()

    post = Post(topic_id=topic.id, author_id=author.id, content="Secret body text")
    db_session.add(post)
    db_session.commit()
    db_session.expire_all()

    raw_title = _raw_value(db_session, "forum_topics", "title", topic.id)
    raw_content = _raw_value(db_session, "forum_posts", "content", post.id)
    assert raw_title.startswith("gAAAAA")
    assert raw_content.startswith("gAAAAA")

    reloaded_topic = db_session.query(Topic).filter(Topic.id == topic.id).first()
    reloaded_post = db_session.query(Post).filter(Post.id == post.id).first()
    assert reloaded_topic.title == "Secret Topic Title"
    assert reloaded_post.content == "Secret body text"


def test_mixed_state_reads_correctly(db_session):
    """A plaintext row written while off still reads back after a key is loaded."""
    # Write plaintext (key inactive).
    author = User(
        email="mixed@example.com",
        password_hash="h",
        first_name="Legacy",
        last_name="Plain",
        role=UserRole.MEMBER,
        is_email_verified=True,
    )
    db_session.add(author)
    db_session.commit()

    # Now activate a key and read the legacy plaintext row.
    key_provider.set_key(encryption.derive_key("pw", encryption.generate_salt()))
    db_session.expire_all()
    reloaded = db_session.query(User).filter(User.id == author.id).first()
    assert reloaded.first_name == "Legacy"
    assert reloaded.last_name == "Plain"

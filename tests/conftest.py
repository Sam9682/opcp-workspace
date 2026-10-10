"""Pytest configuration and fixtures"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
# Import models so they are registered with Base. Importing Installation and the
# prerequisite models here guarantees they are registered on ``Base.metadata``
# so ``create_all`` builds the installations / prerequisite tables the
# installation-scoped tests rely on.
from app.models import User, UserRole, Topic, Post, Document
from app.models import Installation, PrerequisiteContent, PrerequisiteAnswer  # noqa: F401

# ---------------------------------------------------------------------------
# SQLite compatibility for Postgres-only server defaults.
#
# The installations / prerequisite models declare
# ``server_default=text("gen_random_uuid()")`` for their UUID primary keys,
# which is a PostgreSQL function. Under the SQLite test harness the emitted
# ``CREATE TABLE ... DEFAULT gen_random_uuid()`` DDL is invalid SQLite syntax.
# SQLite never needs that server default anyway because the Python-side
# ``default=uuid.uuid4`` already supplies the id on insert, so we strip the
# unsupported server default from the DDL only for the SQLite dialect. This
# keeps the real PostgreSQL DDL untouched.
# ---------------------------------------------------------------------------
def _strip_pg_only_server_defaults() -> None:
    """Drop ``gen_random_uuid()`` server defaults so SQLite can build the tables.

    The Python-side ``default=uuid.uuid4`` still populates the id on insert, so
    behavior is unchanged for the tests; only the invalid SQLite DDL is avoided.
    """
    for table in Base.metadata.tables.values():
        for column in table.columns:
            server_default = column.server_default
            if server_default is None:
                continue
            text_repr = getattr(getattr(server_default, "arg", None), "text", "")
            if isinstance(text_repr, str) and "gen_random_uuid" in text_repr:
                column.server_default = None


_strip_pg_only_server_defaults()

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(db_session):
    """Create a test user for tests"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def verified_user(db_session):
    """Create a verified test user for tests"""
    from app.auth.password import hash_password
    
    user = User(
        email="verified@example.com",
        password_hash=hash_password("SecurePass123"),
        first_name="Verified",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def auth_headers(test_user):
    """Create authentication headers with JWT token"""
    from app.auth.token import create_access_token
    
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Installation-scoped prerequisites helpers.
#
# The prerequisites route family was re-scoped under an installation by the
# ``multi-instance-opcp-prerequisites`` parent spec: content and answers now
# live under ``/api/prerequisites/installations/{installation_id}/{slug}/...``.
# These helpers seed an Installation so the installation-scoped tests can build
# valid paths, plus an id that is guaranteed NOT to exist for negative
# (``INSTALLATION_NOT_FOUND``) coverage.
# ---------------------------------------------------------------------------


def create_installation(db, project_name: str = "Test Installation") -> Installation:
    """Persist and return an Installation on the given session."""
    installation = Installation(project_name=project_name)
    db.add(installation)
    db.commit()
    db.refresh(installation)
    return installation


@pytest.fixture(scope="function")
def installation(db_session) -> Installation:
    """Create a single valid Installation for installation-scoped tests."""
    return create_installation(db_session, "Prereq Test Installation")


@pytest.fixture(scope="function")
def installation_id(installation) -> str:
    """The string UUID of the seeded Installation (for building paths)."""
    return str(installation.id)


@pytest.fixture(scope="function")
def unknown_installation_id() -> str:
    """A syntactically valid UUID that does not match any Installation."""
    return str(uuid.uuid4())

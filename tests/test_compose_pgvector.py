"""Compose smoke tests for the pgvector-doc-embeddings feature.

Feature: pgvector-doc-embeddings

Covers optional test task:
- 1.2  compose smoke tests (Req 1.1, 1.4, 4.8)

These tests parse the repo-root ``docker-compose.yml`` with PyYAML and assert
the infrastructure surface introduced in task 1.1:

- the ``postgres`` service uses the pgvector-enabled PG15 image and retains the
  existing ``shai_db`` database name, ``shai_user`` user, ``pg_isready``
  healthcheck, and ``postgres_data`` volume (Req 1.1, 1.4);
- the one-off ``ingest`` service exists under the ``ingest`` Compose profile and
  runs ``python -m scripts.ingest_embeddings`` (Req 4.8).
"""
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def compose():
    """Parse the repo-root docker-compose.yml once for the whole module."""
    text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


@pytest.fixture(scope="module")
def services(compose):
    services = compose.get("services")
    assert isinstance(services, dict), "docker-compose.yml must define services"
    return services


# ===========================================================================
# Task 1.2 — postgres service uses pgvector and retains existing config
# Requirements: 1.1, 1.4
# ===========================================================================

class TestPostgresService:
    def test_postgres_service_exists(self, services):
        assert "postgres" in services, "postgres service must be defined"

    def test_postgres_uses_pgvector_pg15_image(self, services):
        """Req 1.1: pgvector-enabled image at PostgreSQL major version 15."""
        assert services["postgres"]["image"] == "pgvector/pgvector:pg15"

    def test_postgres_retains_database_name(self, services):
        """Req 1.4: existing shai_db database name retained."""
        env = services["postgres"]["environment"]
        assert env["POSTGRES_DB"] == "shai_db"

    def test_postgres_retains_user(self, services):
        """Req 1.4: existing shai_user user retained."""
        env = services["postgres"]["environment"]
        assert env["POSTGRES_USER"] == "shai_user"

    def test_postgres_retains_pg_isready_healthcheck(self, services):
        """Req 1.4: pg_isready healthcheck retained."""
        healthcheck = services["postgres"].get("healthcheck")
        assert healthcheck is not None, "postgres healthcheck must be present"
        test = healthcheck["test"]
        # `test` may be a string or a CMD/CMD-SHELL list; normalise to text.
        test_text = " ".join(test) if isinstance(test, list) else str(test)
        assert "pg_isready" in test_text

    def test_postgres_retains_data_volume(self, services, compose):
        """Req 1.4: postgres_data volume retained and mounted."""
        # The named volume is declared at the top level.
        assert "postgres_data" in compose.get("volumes", {})
        # And it is mounted by the postgres service.
        mounts = services["postgres"].get("volumes", [])
        assert any(
            str(mount).startswith("postgres_data:") for mount in mounts
        ), "postgres_data volume must be mounted by the postgres service"


# ===========================================================================
# Task 1.2 — one-off ingest service under the ingest profile
# Requirements: 4.8
# ===========================================================================

class TestIngestService:
    def test_ingest_service_exists(self, services):
        assert "ingest" in services, "ingest service must be defined"

    def test_ingest_service_under_ingest_profile(self, services):
        """Req 4.8: ingest runs under the `ingest` Compose profile."""
        profiles = services["ingest"].get("profiles")
        assert profiles is not None, "ingest service must declare profiles"
        assert "ingest" in profiles

    def test_ingest_service_command_runs_module(self, services):
        """Req 4.8: ingest invokes `python -m scripts.ingest_embeddings`."""
        command = services["ingest"].get("command")
        assert command is not None, "ingest service must define a command"
        command_text = (
            " ".join(command) if isinstance(command, list) else str(command)
        )
        assert "python" in command_text
        assert "-m" in command_text
        assert "scripts.ingest_embeddings" in command_text

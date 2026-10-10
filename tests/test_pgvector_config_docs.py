"""Config and env-documentation tests for the pgvector-doc-embeddings feature.

Feature: pgvector-doc-embeddings
Covers optional test task:
- 1.6  Config and env documentation tests

These tests are intentionally complementary to the existing assertions in
`tests/test_opcp_companion_provider.py`:
- `test_settings_defaults_match_rag_query` already asserts the reconciled
  `Settings` defaults (PG_HOST/PG_PORT/PG_DB/PG_USER/TABLE_NAME).
- `test_env_example_documents_each_rag_var` already asserts `.env.example`
  documents each RAG var.

To avoid duplicating those, this module adds the parts NOT covered there:
- the DATABASE_URL-vs-PG_* alignment check (Req 2.5),
- the `.env.prod.example` documentation check (Req 2.6, 6.5),
- the `pypdf`-in-requirements check (Req 4.3).
"""
import re
from pathlib import Path
from urllib.parse import urlparse

from app.config import Settings


REPO_ROOT = Path(__file__).resolve().parents[1]


# ===========================================================================
# Task 1.6 — DATABASE_URL vs PG_* alignment (Req 2.1, 2.2, 2.5)
# ===========================================================================

class TestDatabaseUrlPgAlignment:
    def test_pg_host_and_db_match_database_url(self):
        """WHERE DATABASE_URL and PG_Config both target PostgreSQL, PG_Config
        references the same database (shai_db) and same service as DATABASE_URL.

        Validates: Requirements 2.1, 2.2, 2.5
        """
        s = Settings()
        parsed = urlparse(s.DATABASE_URL)

        # Only meaningful when DATABASE_URL points at PostgreSQL.
        assert parsed.scheme.startswith("postgres"), (
            f"DATABASE_URL is not a PostgreSQL URL: {s.DATABASE_URL!r}"
        )

        url_host = parsed.hostname
        url_db = parsed.path.lstrip("/")

        assert url_host == s.PG_HOST, (
            f"DATABASE_URL host {url_host!r} does not match PG_HOST {s.PG_HOST!r}"
        )
        assert url_db == s.PG_DB, (
            f"DATABASE_URL db {url_db!r} does not match PG_DB {s.PG_DB!r}"
        )
        # And the reconciled canonical values.
        assert s.PG_HOST == "postgres"
        assert s.PG_DB == "shai_db"


# ===========================================================================
# Task 1.6 — .env.prod.example documents PG_* and OVH RAG vars (Req 2.6, 6.5)
# ===========================================================================

class TestEnvProdExampleDocumentation:
    def test_env_prod_example_documents_pg_and_ovh_vars(self):
        """`.env.prod.example` documents the PG_* and OVH RAG variables with
        the reconciled values.

        Validates: Requirements 2.6, 6.5
        """
        env_text = (REPO_ROOT / ".env.prod.example").read_text(encoding="utf-8")

        # Exact reconciled values.
        for line in ("PG_HOST=postgres", "PG_DB=shai_db", "PG_USER=shai_user"):
            assert re.search(rf"^{re.escape(line)}\b", env_text, re.MULTILINE), (
                f"{line!r} not documented in .env.prod.example"
            )

        # Present as documented keys (value unconstrained).
        for var in ("PG_PORT", "PG_PASSWORD", "OVH_AI_ENDPOINT", "OVH_AI_TOKEN"):
            assert re.search(rf"^{var}=", env_text, re.MULTILINE), (
                f"{var} not documented in .env.prod.example"
            )


# ===========================================================================
# Task 1.6 — pypdf declared in requirements.txt (Req 4.3)
# ===========================================================================

class TestRequirementsDeclaresPypdf:
    def test_requirements_declares_pypdf(self):
        """`pypdf` is declared in requirements.txt for PDF text extraction.

        Validates: Requirements 4.3
        """
        req = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        assert re.search(r"^pypdf\b", req, re.MULTILINE), (
            "pypdf not declared in requirements.txt"
        )

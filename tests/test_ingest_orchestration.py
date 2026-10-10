"""Provision-before-insert and missing-credentials unit tests for ingestion.

Feature: pgvector-doc-embeddings
Covers optional test task:
- 7.2  Write provision-before-insert and missing-credentials unit tests

Design: Testing Strategy -> Example / edge-case unit tests:
    "Provision-before-insert (Req 4.7): assert ensure_vector_store is called
     before any INSERT."
    "Missing credentials (Req 6.2, 6.3): for empty and whitespace
     OVH_AI_ENDPOINT/OVH_AI_TOKEN, assert main() returns non-zero and the
     message names the specific variable."

Two concerns are exercised here:

1. Provisioning-first (Req 4.7): main() must call
   provider.ensure_vector_store(conn) before executing any INSERT statement.
   A fake provider records the relative order of "ensure_vector_store" and the
   first INSERT (via a fake cursor) into a shared list; the test asserts the
   provisioning call appears before the first INSERT.

2. Credential validation (Req 6.2, 6.3): when OVH_AI_ENDPOINT or OVH_AI_TOKEN
   is empty or whitespace-only, main() (through validate_credentials) exits
   non-zero and the stderr message names the specific offending variable, with
   no DB or embedding work attempted.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.ingest_embeddings import main, validate_credentials


# ---------------------------------------------------------------------------
# Fakes for the provisioning-order test
# ---------------------------------------------------------------------------
class _RecordingCursor:
    """Fake psycopg2 cursor that records the *kind* of each SQL statement.

    Only the leading keyword matters for ordering (INSERT vs DELETE vs DDL);
    each executed statement appends a marker to the shared ``calls`` list so the
    test can assert provisioning happens before the first INSERT.
    """

    def __init__(self, calls):
        self._calls = calls

    def execute(self, sql, params=None):
        head = sql.strip().split(None, 1)[0].upper()
        if head == "INSERT":
            self._calls.append("INSERT")
        elif head == "DELETE":
            self._calls.append("DELETE")
        else:
            self._calls.append("SQL")

    def close(self):
        pass


class _RecordingConn:
    """Fake connection handing out recording cursors."""

    def __init__(self, calls):
        self._calls = calls

    def cursor(self):
        return _RecordingCursor(self._calls)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class _RecordingProvider:
    """Fake OpcpCompanionProvider recording ensure_vector_store ordering.

    Reuses the real ``table_name`` and returns a correctly-sized fake embedding
    so ``ingest_file`` performs its INSERT. ``ensure_vector_store`` appends a
    marker so the test can locate it relative to the first INSERT.
    """

    def __init__(self, calls, conn, embedding_dim=4096):
        self._calls = calls
        self._conn = conn
        self.table_name = "md_embeddings"
        self.embedding_dim = embedding_dim

    def _get_pg_connection(self):
        return self._conn

    def ensure_vector_store(self, conn):
        self._calls.append("ensure_vector_store")

    def _get_embed_client(self):
        return SimpleNamespace()

    def _embed_query(self, client, chunk):
        return [0.0] * self.embedding_dim


class TestProvisionBeforeInsert:
    def test_ensure_vector_store_called_before_any_insert(self, tmp_path, monkeypatch):
        """main() provisions the vector store before executing any INSERT.

        Validates: Requirements 4.7
        """
        # A docs layout with a single Markdown file so exactly one file is
        # ingested and at least one INSERT is issued.
        docs_dir = tmp_path / "docs"
        pdf_dir = docs_dir / "to_publish"
        docs_dir.mkdir(parents=True)
        pdf_dir.mkdir(parents=True)
        (docs_dir / "guide.md").write_text("Some ingestible content.", encoding="utf-8")

        calls: list[str] = []
        conn = _RecordingConn(calls)

        # Valid OVH credentials so credential validation passes and we reach
        # the provisioning/insert path. main() imports settings/provider lazily
        # from their home modules, so patch them there.
        from app.config import settings as app_settings
        monkeypatch.setattr(app_settings, "OVH_AI_ENDPOINT", "https://ovh.example/v1", raising=False)
        monkeypatch.setattr(app_settings, "OVH_AI_TOKEN", "tok", raising=False)
        monkeypatch.setattr(app_settings, "DOCS_SEED_DIR", str(pdf_dir), raising=False)

        provider = _RecordingProvider(calls, conn)
        import app.oracle.ai_providers as ai_providers
        monkeypatch.setattr(
            ai_providers, "OpcpCompanionProvider", lambda: provider, raising=True
        )

        exit_code = main()

        assert exit_code == 0, f"expected clean run, got exit code {exit_code}"

        assert "ensure_vector_store" in calls, (
            "ensure_vector_store was never called"
        )
        assert "INSERT" in calls, (
            "no INSERT was executed, so ordering cannot be verified"
        )

        provisioning_idx = calls.index("ensure_vector_store")
        first_insert_idx = calls.index("INSERT")
        assert provisioning_idx < first_insert_idx, (
            "ensure_vector_store must be called before any INSERT.\n"
            f"  call order: {calls}"
        )


# ---------------------------------------------------------------------------
# Missing-credentials tests
# ---------------------------------------------------------------------------
def _guard_no_db(monkeypatch):
    """Fail loudly if credential validation lets DB/embedding work start."""
    import app.oracle.ai_providers as ai_providers

    def _should_not_run(*args, **kwargs):
        raise AssertionError(
            "no provider/DB work must be attempted when credentials are missing"
        )

    monkeypatch.setattr(
        ai_providers, "OpcpCompanionProvider", _should_not_run, raising=True
    )


class TestMissingCredentials:
    @pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
    @pytest.mark.parametrize("missing_var", ["OVH_AI_ENDPOINT", "OVH_AI_TOKEN"])
    def test_main_exits_nonzero_naming_missing_variable(
        self, blank, missing_var, monkeypatch, capsys
    ):
        """Empty/whitespace OVH_AI_ENDPOINT/OVH_AI_TOKEN -> non-zero exit naming it.

        validate_credentials calls sys.exit(1), so main() raises SystemExit; the
        exit code must be non-zero and stderr must name the specific variable.
        No DB or embedding work is attempted.

        Validates: Requirements 6.2, 6.3
        """
        from app.config import settings as app_settings

        # Both start valid; blank out exactly the one under test.
        monkeypatch.setattr(app_settings, "OVH_AI_ENDPOINT", "https://ovh.example/v1", raising=False)
        monkeypatch.setattr(app_settings, "OVH_AI_TOKEN", "tok", raising=False)
        monkeypatch.setattr(app_settings, missing_var, blank, raising=False)

        _guard_no_db(monkeypatch)

        with pytest.raises(SystemExit) as exc:
            main()

        # Non-zero exit (SystemExit(1) -> code == 1).
        assert exc.value.code not in (0, None), (
            f"expected non-zero exit for blank {missing_var!r}, got {exc.value.code!r}"
        )

        err = capsys.readouterr().err
        assert missing_var in err, (
            f"stderr should name the missing variable {missing_var!r}; got: {err!r}"
        )

    @pytest.mark.parametrize("blank", ["", "   "])
    @pytest.mark.parametrize("missing_var", ["OVH_AI_ENDPOINT", "OVH_AI_TOKEN"])
    def test_validate_credentials_exits_nonzero_naming_variable(
        self, blank, missing_var, capsys
    ):
        """validate_credentials directly exits non-zero and names the variable.

        Validates: Requirements 6.2, 6.3
        """
        fake_settings = SimpleNamespace(
            OVH_AI_ENDPOINT="https://ovh.example/v1",
            OVH_AI_TOKEN="tok",
        )
        setattr(fake_settings, missing_var, blank)

        with pytest.raises(SystemExit) as exc:
            validate_credentials(fake_settings)

        assert exc.value.code not in (0, None), (
            f"expected non-zero exit for blank {missing_var!r}, got {exc.value.code!r}"
        )

        err = capsys.readouterr().err
        assert missing_var in err, (
            f"stderr should name the missing variable {missing_var!r}; got: {err!r}"
        )

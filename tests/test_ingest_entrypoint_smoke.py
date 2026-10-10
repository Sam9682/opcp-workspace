"""Entry-point smoke test for the ingestion script.

Feature: pgvector-doc-embeddings
Covers optional test task:
- 7.4  Write entry-point smoke test (Req 4.1, 4.8)

Design: Testing Strategy -> Config / smoke tests.

These lightweight assertions confirm the ingestion entry point exists and is
wired the way the design requires, without exercising any DB, embedding, or
filesystem ingestion work:

- ``scripts/ingest_embeddings.py`` exists at the expected location (Req 4.1);
- the module carries the ``if __name__ == "__main__":`` guard that makes it
  independently invocable / runnable as a Docker Compose one-off (Req 4.1, 4.8);
- ``from scripts.ingest_embeddings import main`` yields an importable callable
  (Req 4.1, 4.8).
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ingest_embeddings.py"


class TestIngestionEntryPoint:
    def test_script_file_exists(self):
        """Req 4.1: the ingestion script exists at scripts/ingest_embeddings.py."""
        assert SCRIPT_PATH.is_file(), (
            f"ingestion script must exist at {SCRIPT_PATH}"
        )

    def test_script_has_main_guard(self):
        """Req 4.1, 4.8: the script has a `__main__` guard so it is independently
        invocable and runnable as a Docker Compose one-off task."""
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        assert re.search(
            r'^if\s+__name__\s*==\s*["\']__main__["\']\s*:',
            source,
            re.MULTILINE,
        ), "scripts/ingest_embeddings.py must define an `if __name__ == '__main__':` guard"

    def test_main_is_importable_callable(self):
        """Req 4.1, 4.8: `from scripts.ingest_embeddings import main` yields a
        callable entry point."""
        from scripts.ingest_embeddings import main

        assert callable(main), "scripts.ingest_embeddings.main must be callable"

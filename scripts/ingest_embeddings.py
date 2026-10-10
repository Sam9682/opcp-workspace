"""Standalone RAG document ingestion script.

Discovers Markdown and PDF documents, extracts and chunks their text, embeds each
chunk via the OVH AI Endpoint (reusing ``OpcpCompanionProvider``), and upserts rows
into the ``md_embeddings`` table idempotently.

Runnable as a module::

    python -m scripts.ingest_embeddings

or as a Docker Compose one-off task (see docker-compose.yml ``ingest`` service).

The function bodies below are intentionally left as stubs; later tasks implement
``discover_documents``, ``extract_text``, ``chunk_text``, ``ingest_file`` and
``validate_credentials``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DocFile:
    """An in-memory descriptor for a discovered document to ingest."""

    path: Path  # file path -> stored as file_path
    title: str  # display title, e.g. path.stem
    kind: str  # "md" | "pdf"


def discover_documents(docs_dir: Path, pdf_dir: Path) -> list[DocFile]:
    """Return .md files under docs_dir plus .pdf files under pdf_dir (Req 4.2).

    Discovery is intentionally narrow (Design §5, Property 2):

    - Markdown documents are the ``*.md`` files located *directly* under
      ``docs_dir`` (no recursion, so nested files such as those under
      ``docs/to_publish/`` are not picked up as Markdown).
    - PDF documents are the ``*.pdf`` files located *directly* under
      ``pdf_dir`` (``docs/to_publish/``).

    Files of any other extension, and files in any other location, are
    excluded. Each returned :class:`DocFile` carries the file ``path``, a
    ``title`` derived from ``path.stem``, and a ``kind`` of ``"md"`` or
    ``"pdf"``. Results are sorted by path for deterministic ordering.
    """
    docs: list[DocFile] = []

    if docs_dir.is_dir():
        for entry in sorted(docs_dir.iterdir()):
            if entry.is_file() and entry.suffix.lower() == ".md":
                docs.append(DocFile(path=entry, title=entry.stem, kind="md"))

    if pdf_dir.is_dir():
        for entry in sorted(pdf_dir.iterdir()):
            if entry.is_file() and entry.suffix.lower() == ".pdf":
                docs.append(DocFile(path=entry, title=entry.stem, kind="pdf"))

    return docs


def extract_text(doc: DocFile) -> str:
    """Read .md as UTF-8 text; extract .pdf text via pypdf (Req 4.3).

    Markdown documents are read directly as UTF-8 text. PDF documents have
    their text extracted page-by-page via ``pypdf`` and concatenated in page
    order (Design §5 "PDF text extraction"; Ingestion Sequence step 7).

    The returned string is the raw document text, ready to be chunked by
    :func:`chunk_text`.
    """
    if doc.kind == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(doc.path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)

    return doc.path.read_text(encoding="utf-8")


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """Split ``text`` into contiguous fixed-size character chunks (Req 4.4).

    Chunks are produced in document order with a small overlap between
    consecutive chunks (Design §5 "Chunking strategy"). The chunk at position
    ``i`` in the returned list carries ``chunk_index == i``, so indices form the
    contiguous sequence ``0, 1, ..., n-1`` (Property 3).

    Contiguity/coverage guarantee (Property 3): consecutive chunks advance by
    ``step = chunk_size - overlap`` characters. The non-overlapping portion of
    each chunk is its first ``step`` characters; concatenating those portions
    for every chunk except the last, followed by the entire last chunk,
    reconstructs the input exactly with no gaps. Because ``step >= 1`` the
    window always moves forward and the final partial chunk captures any
    remaining tail.

    Edge cases:

    - Empty ``text`` -> ``[]`` (no chunks to embed).
    - ``text`` shorter than (or equal to) ``chunk_size`` -> a single chunk
      containing the whole text.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    if not text:
        return []

    step = chunk_size - overlap
    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        chunks.append(text[start : start + chunk_size])
        # Once a chunk reaches the end of the text, we are done. Advancing
        # again would only emit a chunk fully contained in this one (a
        # redundant, entirely-overlapping tail), so stop here.
        if start + chunk_size >= length:
            break
        start += step

    return chunks


def ingest_file(conn, provider, embed_client, doc: DocFile) -> int:
    """Upsert all chunks for one file; returns chunk count (Req 4.5, 4.6, 5.1, 5.2).

    Extracts and chunks the document, embeds each chunk through the provider's
    OVH embedding path, and idempotently replaces the document's rows in the
    ``md_embeddings`` table (Design §5 "Embedding", "Idempotent upsert",
    "Vector serialization"; Ingestion Sequence steps 4-7).

    The provider is assumed to have already provisioned the vector store via
    ``ensure_vector_store(conn)`` (orchestrated in ``main``), so the extension
    and table exist before any insert (Req 4.7).

    Upsert semantics (Req 5.1, 5.2): within a single per-file transaction, all
    existing rows for this document's ``file_path`` are deleted, then the freshly
    produced chunks are inserted. Delete-then-insert guarantees no duplicate
    ``(file_path, chunk_index)`` rows across re-runs and drops now-obsolete
    trailing chunks when a document shrinks. The transaction is committed once
    per file so re-runs are atomic per document.

    Embedding (Req 4.5, 6.4): each chunk is embedded via
    ``provider._embed_query(embed_client, chunk)`` (``EMBEDDING_MODEL``
    Qwen3-Embedding-8B, validated against ``EMBEDDING_DIM`` = 4096). The vector
    is serialized to the pgvector ``"[v1,v2,...]"`` string form and cast with
    ``%s::vector`` in the INSERT — mirroring ``OpcpCompanionProvider._search``.

    The table name comes from configuration (``provider.table_name``), never
    from user input, so its interpolation into the SQL is safe (same pattern as
    the provider's query path); all values are passed as ``%s`` parameters.

    Returns the number of chunks stored for this file.
    """
    text = extract_text(doc)
    chunks = chunk_text(text)

    # Consistent string form of the source path used as the delete-then-insert key.
    file_path = str(doc.path)

    table = provider.table_name
    delete_sql = f"DELETE FROM {table} WHERE file_path = %s"
    insert_sql = (
        f"INSERT INTO {table} "
        "(title, file_path, chunk_index, content, embedding) "
        "VALUES (%s, %s, %s, %s, %s::vector)"
    )

    cursor = conn.cursor()
    try:
        cursor.execute(delete_sql, (file_path,))
        for chunk_index, chunk in enumerate(chunks):
            vector = provider._embed_query(embed_client, chunk)
            # pgvector serialization: "[v1,v2,...]" — same format as _search.
            vector_str = "[" + ",".join(str(v) for v in vector) + "]"
            cursor.execute(
                insert_sql,
                (doc.title, file_path, chunk_index, chunk, vector_str),
            )
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()

    conn.commit()
    return len(chunks)


def validate_credentials(settings) -> None:
    """Exit non-zero if OVH_AI_ENDPOINT or OVH_AI_TOKEN is missing/blank (Req 6.1-6.3).

    Reads ``settings.OVH_AI_ENDPOINT`` and ``settings.OVH_AI_TOKEN`` before any
    DB connection or embedding work is attempted (Design §5 "Credential
    validation"; Ingestion Sequence step 1). A value is considered missing when
    it is ``None``, empty, or whitespace-only. On failure, an error naming the
    specific offending variable is printed to stderr and the process exits with
    a non-zero code (``1``); no partial ingestion is performed.
    """
    for name in ("OVH_AI_ENDPOINT", "OVH_AI_TOKEN"):
        value = getattr(settings, name, None)
        if value is None or not str(value).strip():
            print(f"ERROR: {name} is not set", file=sys.stderr)
            sys.exit(1)


def main() -> int:
    """Orchestrate ingestion; return the process exit code (Req 4.7, 6.1-6.4).

    Follows the Ingestion Sequence (Design §5 / "Ingestion Sequence"):

    1. Validate OVH credentials up front (non-zero exit on failure).
    2. Construct the ``OpcpCompanionProvider``.
    3. Open the psycopg2 connection via ``provider._get_pg_connection()``.
    4. Provision the vector store with ``provider.ensure_vector_store(conn)``
       *before* any insert (Req 4.7).
    5. Build the embed client via ``provider._get_embed_client()``.
    6. Discover documents: Markdown from the docs root, PDFs from
       ``docs_root/to_publish`` (derived from ``settings.DOCS_SEED_DIR``).
    7. Ingest each file, continuing past a failing document (e.g. a bad PDF) but
       marking the run as failed so the exit code is non-zero if any file failed.
    8. Close the connection and return the exit code.
    """
    from app.config import settings
    from app.oracle.ai_providers import OpcpCompanionProvider

    # Step 1: credential validation (exits non-zero on failure).
    validate_credentials(settings)

    # Resolve the docs directories from configuration. DOCS_SEED_DIR points at
    # the PDF publication folder (docs/to_publish); its parent is the docs root
    # holding the top-level Markdown files.
    pdf_dir = Path(settings.DOCS_SEED_DIR)
    docs_dir = pdf_dir.parent

    # Step 2: construct the provider.
    provider = OpcpCompanionProvider()

    # Step 3: open the connection.
    conn = provider._get_pg_connection()

    total_chunks = 0
    files_processed = 0
    failed_files: list[str] = []

    try:
        # Step 4: provision the vector store before any insert (Req 4.7).
        provider.ensure_vector_store(conn)

        # Step 5: build the embed client.
        embed_client = provider._get_embed_client()

        # Step 6: discover documents.
        docs = discover_documents(docs_dir, pdf_dir)

        # Step 7: ingest each file; keep going past a bad document.
        for doc in docs:
            try:
                chunks_stored = ingest_file(conn, provider, embed_client, doc)
            except Exception as exc:  # noqa: BLE001 - report and continue
                failed_files.append(str(doc.path))
                print(
                    f"ERROR: failed to ingest {doc.path}: {exc}",
                    file=sys.stderr,
                )
                continue
            files_processed += 1
            total_chunks += chunks_stored
            print(f"Ingested {doc.path} ({chunks_stored} chunks)")
    finally:
        # Step 8: always close the connection.
        try:
            conn.close()
        except Exception:
            pass

    # Summary to stdout.
    print(
        f"Summary: {files_processed} file(s) processed, "
        f"{total_chunks} chunk(s) stored."
    )
    if failed_files:
        print(
            f"Summary: {len(failed_files)} file(s) failed: "
            + ", ".join(failed_files),
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Property-based test for document discovery in the ingestion script.

Feature: pgvector-doc-embeddings
Property 2: Document discovery selects exactly the intended files
Validates: Requirements 4.2

For any documentation directory layout, the set of documents discovered by the
ingestion script equals exactly the Markdown files located *directly* under
``docs/`` together with the PDF files located *directly* under
``docs/to_publish/``, and excludes files of any other extension or in any other
location (Design §5 "Document discovery"; Correctness Properties → Property 2).

The generator builds a temp directory tree mixing ``.md``, ``.pdf``, and other
extensions across:
- files directly under ``docs_dir`` (only ``.md`` here should be selected),
- files directly under ``pdf_dir`` (only ``.pdf`` here should be selected),
- files in a nested subdirectory under ``docs_dir`` (never selected),
- files directly under a sibling directory outside both roots (never selected).

Then it asserts ``discover_documents(docs_dir, pdf_dir)`` returns exactly the
expected DocFile set (path/title/kind), independent of ordering.

Runs with at least 100 Hypothesis iterations.
"""
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scripts.ingest_embeddings import DocFile, discover_documents


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
# File "stems" (base names without extension): safe, filesystem-friendly,
# non-empty, and unique-able. Kept ASCII and free of path separators / dots so
# the extension we append is unambiguous.
_stem = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_",
    min_size=1,
    max_size=16,
).filter(lambda s: s.strip("-_") != "")

# A mix of extensions: the two "intended" ones plus several that must never be
# selected regardless of where they live.
_extension = st.sampled_from([".md", ".pdf", ".txt", ".doc", ".markdown", ".pd", ".mdx", ""])

# A single (stem, extension) file spec.
_file_spec = st.tuples(_stem, _extension)

# Lists of file specs for each location in the layout. Small bounds keep each
# example fast while still producing a rich mix across 100+ iterations.
_file_specs = st.lists(_file_spec, min_size=0, max_size=8)


@st.composite
def _layouts(draw):
    """Generate a directory layout across four locations.

    Returns a dict with the file specs to materialize under:
    - "docs_top":    directly under docs_dir
    - "pdf_top":     directly under pdf_dir (docs/to_publish/)
    - "docs_nested": under a nested subdir of docs_dir (docs/nested/)
    - "outside":     directly under a sibling dir outside both roots
    """
    return {
        "docs_top": draw(_file_specs),
        "pdf_top": draw(_file_specs),
        "docs_nested": draw(_file_specs),
        "outside": draw(_file_specs),
    }


def _write_files(directory: Path, specs) -> None:
    """Materialize (stem, ext) specs as empty files under ``directory``.

    De-duplicates by final filename so two specs colliding on the same name do
    not raise; the resulting on-disk set is what discovery must match.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for stem, ext in specs:
        (directory / f"{stem}{ext}").write_text("", encoding="utf-8")


# ===========================================================================
# Property 2: discover_documents selects exactly the intended files.
# ===========================================================================
@settings(max_examples=150, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(layout=_layouts())
def test_discover_documents_selects_exactly_intended_files(tmp_path_factory, layout):
    """discover_documents returns exactly ``docs/*.md`` + ``docs/to_publish/*.pdf``.

    Validates: Requirements 4.2
    """
    root = tmp_path_factory.mktemp("layout")
    docs_dir = root / "docs"
    pdf_dir = docs_dir / "to_publish"
    nested_dir = docs_dir / "nested"
    outside_dir = root / "elsewhere"

    _write_files(docs_dir, layout["docs_top"])
    _write_files(pdf_dir, layout["pdf_top"])
    _write_files(nested_dir, layout["docs_nested"])
    _write_files(outside_dir, layout["outside"])

    # Expected set, computed from what actually landed on disk (after any
    # filename collisions), applying the narrow selection rule:
    #   - .md files directly under docs_dir
    #   - .pdf files directly under pdf_dir
    expected = set()
    for entry in docs_dir.iterdir():
        if entry.is_file() and entry.suffix.lower() == ".md":
            expected.add((entry, entry.stem, "md"))
    for entry in pdf_dir.iterdir():
        if entry.is_file() and entry.suffix.lower() == ".pdf":
            expected.add((entry, entry.stem, "pdf"))

    result = discover_documents(docs_dir, pdf_dir)

    # Each result must be a DocFile.
    assert all(isinstance(d, DocFile) for d in result)

    result_set = {(d.path, d.title, d.kind) for d in result}

    assert result_set == expected, (
        "COUNTEREXAMPLE: discovery did not select exactly the intended files.\n"
        f"  missing (expected, not returned): {expected - result_set}\n"
        f"  extra   (returned, not expected): {result_set - expected}"
    )

    # No duplicates in the returned list.
    assert len(result) == len(result_set), (
        f"COUNTEREXAMPLE: duplicate DocFiles returned: {result}"
    )

    # Exclusion invariants: nothing from nested or outside locations, and no
    # non-intended extension leaks through.
    for d in result:
        assert d.kind in ("md", "pdf")
        if d.kind == "md":
            assert d.path.parent == docs_dir
            assert d.path.suffix.lower() == ".md"
        else:
            assert d.path.parent == pdf_dir
            assert d.path.suffix.lower() == ".pdf"

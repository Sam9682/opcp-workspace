"""Property-based and unit tests for the pure helpers in document_seed_service.

Feature: docs-auto-seed-and-documents-page
Updated for: documents-page-categories (BUGFIX)

These tests cover the helpers that need no database:
  - resolve_mime_type       (Property 1: MIME resolution mapping)
  - infer_category          (Property 2: subfolder-based category inference)
  - discover_source_files   (recursive, tuple-returning discovery)

NOTE (documents-page-categories bugfix): the category-inference behavior
deliberately changed. ``infer_category`` no longer inspects the filename
extension/keywords; it now takes the file's *originating subfolder* under
``docs/to_publish`` and maps it to the matching ``DocumentCategory``. Likewise
``discover_source_files`` is now recursive and returns ``(Path, subfolder)``
tuples restricted to the four content subfolders. The former keyword-based
category tests and the enum members they referenced (STATUTES, MINUTES,
FINANCIAL_REPORTS, OTHER) no longer exist and have been rewritten below to
assert the new subfolder-based behavior. The MIME-resolution tests are
unchanged (that behavior was not touched by the bugfix).
"""
import pytest
from hypothesis import given, settings, strategies as st

from app.services.document_seed_service import (
    resolve_mime_type,
    infer_category,
    discover_source_files,
    CATEGORY_BY_SUBFOLDER,
    CONTENT_SUBFOLDERS,
    DEFAULT_MIME,
)
from app.models.document import DocumentCategory


# Known extensions and their expected MIME types (Requirements 3.1-3.4).
KNOWN_EXTENSIONS = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
}

# Base-name strategy: arbitrary text that does not itself introduce a
# recognised extension. We forbid '.' and path separators so the base name
# never accidentally becomes the file's suffix.
base_name_strategy = st.text(
    alphabet=st.characters(blacklist_characters="./\\", blacklist_categories=("Cs",)),
    min_size=0,
    max_size=40,
)

# Non-empty base name for cases where we append a real extension. A leading-dot
# name (e.g. ".doc") is treated by pathlib as a dotfile with no suffix, so a
# non-empty base is what makes the trailing token an actual extension.
non_empty_base_strategy = st.text(
    alphabet=st.characters(blacklist_characters="./\\", blacklist_categories=("Cs",)),
    min_size=1,
    max_size=40,
)


def _mix_case(ext: str, seed: int) -> str:
    """Deterministically produce a mixed-case variant of an extension."""
    out = []
    for i, ch in enumerate(ext):
        out.append(ch.upper() if (seed >> i) & 1 else ch.lower())
    return "".join(out)


# ---------------------------------------------------------------------------
# Property 1: MIME resolution mapping
# Feature: docs-auto-seed-and-documents-page
# Validates: Requirements 3.1, 3.2, 3.3, 3.4
# ---------------------------------------------------------------------------

@pytest.mark.property
@settings(max_examples=200)
@given(
    base=non_empty_base_strategy,
    ext=st.sampled_from(sorted(KNOWN_EXTENSIONS.keys())),
    case_seed=st.integers(min_value=0, max_value=15),
)
def test_property_known_extension_maps_to_expected_mime(base, ext, case_seed):
    """Property 1: any known extension resolves to its fixed MIME type,
    independent of the base name and of the extension's letter case.

    Validates Requirements 3.1, 3.2, 3.3, 3.4.
    """
    expected = KNOWN_EXTENSIONS[ext]
    cased_ext = _mix_case(ext, case_seed)
    filename = f"{base}{cased_ext}"

    result = resolve_mime_type(filename)

    assert result == expected
    # Case-insensitive: the mixed-case extension yields the same result as the
    # canonical lower-case extension, and the base name does not affect it.
    assert result == resolve_mime_type(f"file{ext}")
    assert resolve_mime_type(f"{base}{ext}") == resolve_mime_type(f"other{ext}")


@pytest.mark.property
@settings(max_examples=200)
@given(
    base=non_empty_base_strategy,
    other_ext=st.text(
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"),
        ),
        min_size=1,
        max_size=6,
    ),
)
def test_property_unknown_extension_maps_to_default(base, other_ext):
    """Property 1: any extension not in the known set (and the no-extension
    case) resolves to the default 'application/octet-stream'.

    Validates Requirement 3 (default branch of 3.1-3.4).
    """
    ext = f".{other_ext}"
    # Skip cases that happen to be a known extension (case-insensitively).
    if ext.lower() in KNOWN_EXTENSIONS:
        return

    filename = f"{base}{ext}"
    assert resolve_mime_type(filename) == DEFAULT_MIME


@pytest.mark.property
@settings(max_examples=100)
@given(base=base_name_strategy)
def test_property_absent_extension_maps_to_default(base):
    """Property 1: a name with no extension resolves to the default MIME.

    Validates Requirement 3 (absent-extension default).
    """
    # base_name_strategy excludes '.', so `base` has no suffix.
    assert resolve_mime_type(base) == DEFAULT_MIME


def test_known_extension_examples():
    """Targeted examples for each known extension (Requirements 3.1-3.4)."""
    assert resolve_mime_type("statutes.md") == "text/markdown"
    assert resolve_mime_type("notes.txt") == "text/plain"
    assert resolve_mime_type("report.pdf") == "application/pdf"
    assert resolve_mime_type("charter.doc") == "application/msword"
    # Case-insensitivity of the extension.
    assert resolve_mime_type("README.MD") == "text/markdown"
    assert resolve_mime_type("README.Md") == "text/markdown"
    # Unknown / absent extension defaults.
    assert resolve_mime_type("archive.zip") == DEFAULT_MIME
    assert resolve_mime_type("Makefile") == DEFAULT_MIME


# ---------------------------------------------------------------------------
# Property 2: Subfolder-based category inference
# Feature: documents-page-categories (BUGFIX)
# Validates: Requirements 2.2, 2.4
#
# infer_category now maps a file's originating subfolder under
# ``docs/to_publish`` to the corresponding DocumentCategory. The four content
# subfolders (docs, links, scripts, trainings) each map to the category whose
# value equals the subfolder name; any unrecognised subfolder falls back to
# DOCUMENTS for backward compatibility.
# ---------------------------------------------------------------------------

@pytest.mark.property
@settings(max_examples=200)
@given(subfolder=st.sampled_from(sorted(CATEGORY_BY_SUBFOLDER.keys())))
def test_property_content_subfolder_maps_to_matching_category(subfolder):
    """Property 2: each content subfolder maps to the category whose value
    equals the subfolder name, and inference is deterministic.

    Validates Requirements 2.2, 2.4.
    """
    result = infer_category(subfolder)
    # Determinism: same input always yields the same output.
    assert infer_category(subfolder) == result
    # The category value equals the originating subfolder name.
    assert result.value == subfolder
    assert result == CATEGORY_BY_SUBFOLDER[subfolder]


@pytest.mark.property
@settings(max_examples=200)
@given(
    subfolder=st.text(max_size=30).filter(
        lambda s: s not in CATEGORY_BY_SUBFOLDER
    )
)
def test_property_unknown_subfolder_falls_back_to_documents(subfolder):
    """Property 2: any subfolder outside the four content subfolders (including
    the empty string) falls back to the DOCUMENTS category.

    Validates Requirement 2.4 (backward-compatible fallback).
    """
    assert infer_category(subfolder) == DocumentCategory.DOCUMENTS


def test_subfolder_category_examples():
    """Targeted examples for subfolder-based category inference.

    Validates Requirements 2.2, 2.4.
    """
    assert infer_category("docs") == DocumentCategory.DOCS
    assert infer_category("links") == DocumentCategory.LINKS
    assert infer_category("scripts") == DocumentCategory.SCRIPTS
    assert infer_category("trainings") == DocumentCategory.TRAININGS
    # Unknown / empty subfolders fall back to DOCUMENTS.
    assert infer_category("") == DocumentCategory.DOCUMENTS
    assert infer_category("movies") == DocumentCategory.DOCUMENTS
    assert infer_category("images") == DocumentCategory.DOCUMENTS


# ---------------------------------------------------------------------------
# discover_source_files: recursive, tuple-returning, subfolder-restricted
# Feature: documents-page-categories (BUGFIX)
# Validates: Requirement 2.4
# ---------------------------------------------------------------------------

def _write(path):
    """Create a file (and its parents) with trivial content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


def test_discover_returns_files_paired_with_originating_subfolder(tmp_path):
    """discover_source_files pairs each file with its originating content
    subfolder (Requirement 2.4)."""
    docs_dir = tmp_path / "to_publish"
    _write(docs_dir / "docs" / "spec.pdf")
    _write(docs_dir / "links" / "useful.links")
    _write(docs_dir / "scripts" / "deploy.sh")
    _write(docs_dir / "trainings" / "onboarding.md")

    discovered = discover_source_files(docs_dir)

    pairs = {(path.name, subfolder) for path, subfolder in discovered}
    assert pairs == {
        ("spec.pdf", "docs"),
        ("useful.links", "links"),
        ("deploy.sh", "scripts"),
        ("onboarding.md", "trainings"),
    }


def test_discover_recurses_into_nested_subfolders(tmp_path):
    """discover_source_files walks nested directories within a content subfolder
    and retains the top-level originating subfolder (Requirement 2.4)."""
    docs_dir = tmp_path / "to_publish"
    _write(docs_dir / "trainings" / "module-1" / "lesson.md")

    discovered = discover_source_files(docs_dir)

    assert ("lesson.md", "trainings") in {
        (path.name, subfolder) for path, subfolder in discovered
    }


def test_discover_excludes_non_content_subfolders(tmp_path):
    """Files under movies/images (and top-level files) are excluded so they do
    not become category sections (Requirement 2.4)."""
    docs_dir = tmp_path / "to_publish"
    _write(docs_dir / "movies" / "intro.mp4")
    _write(docs_dir / "images" / "logo.png")
    _write(docs_dir / "top_level.md")
    _write(docs_dir / "docs" / "spec.pdf")

    discovered = discover_source_files(docs_dir)

    names = {path.name for path, _ in discovered}
    subfolders = {subfolder for _, subfolder in discovered}
    assert names == {"spec.pdf"}
    assert subfolders <= set(CONTENT_SUBFOLDERS)
    assert "movies" not in subfolders
    assert "images" not in subfolders


def test_discover_missing_directory_returns_empty(tmp_path):
    """A missing docs directory yields no files (no crash)."""
    assert discover_source_files(tmp_path / "does_not_exist") == []


def test_discover_result_is_sorted_deterministically(tmp_path):
    """discover_source_files returns a stable, sorted ordering by
    (subfolder, filename)."""
    docs_dir = tmp_path / "to_publish"
    _write(docs_dir / "scripts" / "b.sh")
    _write(docs_dir / "scripts" / "a.sh")
    _write(docs_dir / "docs" / "z.pdf")

    discovered = discover_source_files(docs_dir)
    keys = [(subfolder, path.name) for path, subfolder in discovered]
    assert keys == sorted(keys)
    # docs sorts before scripts; within scripts, a.sh before b.sh.
    assert keys == [("docs", "z.pdf"), ("scripts", "a.sh"), ("scripts", "b.sh")]

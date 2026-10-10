"""Property-based tests for storage file validation and storage-path invariance.

Feature: admin-document-upload-categories

Property 2: Allowed types are accepted
    Validates: Requirements 4.1

Property 4: Storage path is category-independent
    Validates: Requirements 2.3, 4.2

These Hypothesis-driven properties exercise ``StorageService.validate_file`` and
``StorageService.save_file`` (from ``app.services.storage_service``) across many
generated filenames, extensions, and file sizes/contents.
"""
import uuid
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.document import CATEGORY_MAPPING
from app.services.storage_service import ALLOWED_EXTENSIONS, StorageService


def _make_service(tmp_path) -> StorageService:
    """Build a StorageService whose upload_dir points at an isolated tmp dir.

    ``StorageService.__init__`` reads from the global settings, so after
    construction we redirect ``upload_dir`` at the per-example temp directory to
    keep filesystem writes isolated and deterministic.
    """
    service = StorageService()
    service.upload_dir = Path(tmp_path)
    service.upload_dir.mkdir(parents=True, exist_ok=True)
    return service


# The extensions callers depend on being accepted (design Property 2 explicitly
# calls out md/txt/sh/sql/py in addition to the rest of the allow-list).
_ALLOWED_EXTS = sorted(ALLOWED_EXTENSIONS)


def _mixed_case(draw, ext: str) -> str:
    """Randomly re-case each character to probe case-insensitive validation."""
    flags = draw(st.lists(st.booleans(), min_size=len(ext), max_size=len(ext)))
    return "".join(c.upper() if f else c.lower() for c, f in zip(ext, flags))


@st.composite
def _allowed_filename(draw):
    """Generate a filename whose extension is in ALLOWED_EXTENSIONS."""
    ext = draw(st.sampled_from(_ALLOWED_EXTS))
    cased_ext = _mixed_case(draw, ext)
    stem = draw(
        st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters="_-",
            ),
            min_size=1,
            max_size=20,
        )
    )
    return f"{stem}.{cased_ext}"


@pytest.mark.property
@settings(max_examples=200)
@given(
    filename=_allowed_filename(),
    # Size within the 10MB default max; keep it small enough to be well under.
    file_size=st.integers(min_value=0, max_value=1024 * 1024),
)
def test_validate_file_accepts_allowed_types(tmp_path_factory, filename, file_size):
    """Property 2: allowed extensions within the size limit validate as valid.

    Feature: admin-document-upload-categories, Property 2: Allowed types are
    accepted.
    Validates Requirement 4.1.
    """
    service = _make_service(tmp_path_factory.mktemp("uploads"))
    # The generated size stays well under the configured maximum.
    assert file_size <= service.max_size
    is_valid, error_message = service.validate_file(file_size, filename)
    assert is_valid is True
    assert error_message is None


@st.composite
def _categorized_filename(draw):
    """Generate a filename whose extension maps to a category (documents/scripts/links)."""
    ext = draw(st.sampled_from(sorted(CATEGORY_MAPPING)))
    stem = draw(
        st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters="_-",
            ),
            min_size=1,
            max_size=20,
        )
    )
    return f"{stem}.{ext}"


@pytest.mark.property
@settings(max_examples=200)
@given(
    filename=_categorized_filename(),
    content=st.binary(min_size=0, max_size=4096),
)
def test_save_file_persists_under_upload_dir(tmp_path_factory, filename, content):
    """Property 4: any accepted upload persists under the single UPLOAD_DIR.

    Feature: admin-document-upload-categories, Property 4: Storage path is
    category-independent.
    Validates Requirements 2.3, 4.2.
    """
    service = _make_service(tmp_path_factory.mktemp("uploads"))
    unique_filename, file_path = service.save_file(content, filename)

    resolved = Path(file_path).resolve()
    upload_root = service.upload_dir.resolve()

    # The saved file resides under the configured UPLOAD_DIR regardless of the
    # file's category (extension), and it actually exists on disk there.
    assert resolved.parent == upload_root
    assert resolved == (upload_root / unique_filename).resolve()
    assert resolved.exists()
    # The stored name preserves the original suffix (a UUID stem + extension).
    assert resolved.suffix.lower() == Path(filename).suffix.lower()

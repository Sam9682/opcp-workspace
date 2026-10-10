"""Property-based tests for extension-based document classification.

Feature: admin-document-upload-categories

Property 1: Extension classification matches the mapping
    Validates: Requirements 1.1, 2.1, 2.2

Property 3: Unknown extensions are rejected (classifier portion)
    Validates: Requirements 2.4

These Hypothesis-driven properties exercise ``classify_extension`` (from
``app.models.document``) across many generated filenames.
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.document import (
    CATEGORY_MAPPING,
    DocumentCategory,
    classify_extension,
)

# The complete, mutually-exclusive three-value category set.
_ALL_CATEGORIES = {
    DocumentCategory.DOCUMENTS,
    DocumentCategory.SCRIPTS,
    DocumentCategory.LINKS,
}

# Explicit expectation table derived from the design's Category_Mapping.
_EXPECTED = {
    "pdf": DocumentCategory.DOCUMENTS,
    "doc": DocumentCategory.DOCUMENTS,
    "docx": DocumentCategory.DOCUMENTS,
    "md": DocumentCategory.DOCUMENTS,
    "txt": DocumentCategory.DOCUMENTS,
    "sh": DocumentCategory.SCRIPTS,
    "sql": DocumentCategory.SCRIPTS,
    "py": DocumentCategory.SCRIPTS,
    "links": DocumentCategory.LINKS,
}


def _mixed_case(draw, ext: str) -> str:
    """Randomly re-case each character of ``ext`` to probe case-insensitivity."""
    flags = draw(st.lists(st.booleans(), min_size=len(ext), max_size=len(ext)))
    return "".join(c.upper() if f else c.lower() for c, f in zip(ext, flags))


@st.composite
def _known_filename(draw):
    """Generate (filename, expected_category) for an extension in the mapping."""
    ext = draw(st.sampled_from(sorted(_EXPECTED)))
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
    return f"{stem}.{cased_ext}", _EXPECTED[ext]


@pytest.mark.property
@settings(max_examples=200)
@given(case=_known_filename())
def test_classify_extension_matches_mapping(case):
    """Property 1: mapped extensions classify per the mapping, case-insensitively.

    Feature: admin-document-upload-categories, Property 1: Extension
    classification matches the mapping.
    Validates Requirements 1.1, 2.1, 2.2.
    """
    filename, expected = case
    result = classify_extension(filename)
    assert result == expected
    # Requirement 1.1: the value is always one of the three-value category set.
    assert result in _ALL_CATEGORIES


@st.composite
def _unknown_filename(draw):
    """Generate a filename whose extension is NOT in CATEGORY_MAPPING.

    Covers both a random unmapped extension and the no-extension case.
    """
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
    no_extension = draw(st.booleans())
    if no_extension:
        # Bare stem: no dot, so no extension.
        return stem

    # A random alphanumeric extension, filtered to those not in the mapping.
    ext = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=8,
        ).filter(lambda e: e.lower() not in CATEGORY_MAPPING)
    )
    return f"{stem}.{ext}"


@pytest.mark.property
@settings(max_examples=200)
@given(filename=_unknown_filename())
def test_classify_extension_rejects_unknown(filename):
    """Property 3 (classifier portion): unmapped / missing extensions -> None.

    Feature: admin-document-upload-categories, Property 3: Unknown extensions
    are rejected.
    Validates Requirement 2.4.
    """
    assert classify_extension(filename) is None

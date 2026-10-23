"""Property-based test for export filename construction.

Feature: document-audience-adapter

Property 10: Export filenames identify the source and the audience level
    Validates: Requirements 6.3

For any source name and any ``AudienceLevel``, ``build_export_filename``
(``app.document_adapter.export``) returns a filename that:

- contains a sanitized identifier derived from the source name,
- contains the selected audience level value, and
- ends with the extension matching the requested format (pdf/docx).

The test uses Hypothesis to generate arbitrary source-name strings and samples
over the four ``AudienceLevel`` values and both export formats.
"""
import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.document_adapter.export import build_export_filename
from app.document_adapter.schemas import AudienceLevel

# The two supported export formats and the extension each must produce.
_FORMAT_EXTENSIONS = {"pdf": "pdf", "docx": "docx"}

# Characters allowed in the sanitized stem (mirrors the builder's allow-list).
_ALLOWED_STEM_CHARS = re.compile(r"^[A-Za-z0-9._-]+$")


def _expected_stem(source_name: str) -> str:
    """Compute the sanitized stem the builder is expected to produce.

    Derived independently from the convention in the design (strip extension,
    replace non-``[A-Za-z0-9._-]`` runs with ``_``, collapse repeats, trim
    leading/trailing ``_``, fall back to ``document`` when empty).
    """
    name = source_name or ""
    dot = name.rfind(".")
    stem = name[:dot] if dot > 0 else name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = sanitized.strip("_")
    return sanitized or "document"


@pytest.mark.property
@settings(max_examples=200)
@given(
    source_name=st.text(max_size=120),
    audience=st.sampled_from(list(AudienceLevel)),
    fmt=st.sampled_from(sorted(_FORMAT_EXTENSIONS)),
)
def test_export_filename_identifies_source_and_audience(source_name, audience, fmt):
    """Property 10: Export filenames identify the source and the audience level.

    Feature: document-audience-adapter, Property 10: Export filenames identify
    the source and the audience level.
    Validates Requirements 6.3.
    """
    filename = build_export_filename(source_name, audience, fmt)
    expected_ext = _FORMAT_EXTENSIONS[fmt]

    # Ends with the extension matching the requested format.
    assert filename.endswith(f".{expected_ext}")

    # The name is split into a stem and a (single) trailing extension.
    stem, dot, ext = filename.rpartition(".")
    assert dot == "."
    assert ext == expected_ext

    # The stem encodes the sanitized source identifier plus the audience value,
    # joined by the ``__`` separator from the convention.
    assert stem == f"{_expected_stem(source_name)}__{audience.value}"

    # Contains the selected audience level value.
    assert audience.value in filename

    # Contains a non-empty sanitized source identifier that only uses the
    # allowed filename character set.
    source_identifier = _expected_stem(source_name)
    assert source_identifier
    assert source_identifier in filename
    assert _ALLOWED_STEM_CHARS.match(source_identifier)


@pytest.mark.property
@settings(max_examples=100)
@given(
    source_name=st.text(max_size=120),
    audience=st.sampled_from(list(AudienceLevel)),
    fmt=st.sampled_from(sorted(_FORMAT_EXTENSIONS)),
)
def test_export_filename_accepts_raw_audience_string(source_name, audience, fmt):
    """The audience value is honored whether passed as enum or raw string.

    Feature: document-audience-adapter, Property 10: Export filenames identify
    the source and the audience level.
    Validates Requirements 6.3.
    """
    from_enum = build_export_filename(source_name, audience, fmt)
    from_str = build_export_filename(source_name, audience.value, fmt)
    assert from_enum == from_str

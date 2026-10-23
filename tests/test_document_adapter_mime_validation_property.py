"""Property-based tests for Document Audience Adapter MIME validation.

Feature: document-audience-adapter

Property 1: Only PDF and Word source files are accepted
    Validates: Requirements 2.4

``is_supported_source_type`` (from ``app.document_adapter.extraction``) must
return ``True`` iff the given string is exactly one of the three supported
source MIME types (PDF, legacy Word, Word OpenXML), and ``False`` for every
other string. These Hypothesis-driven properties exercise the predicate across
many generated MIME-type strings.
"""
from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

from app.document_adapter.extraction import (
    SUPPORTED_SOURCE_MIME_TYPES,
    is_supported_source_type,
)

# The exact, closed set of supported source MIME types (PDF + Word variants).
_SUPPORTED = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)


def test_supported_set_matches_expectation():
    """Guard: the module's supported set is exactly the three expected types."""
    assert set(SUPPORTED_SOURCE_MIME_TYPES) == set(_SUPPORTED)


@pytest.mark.property
@settings(max_examples=200)
@given(mime_type=st.sampled_from(sorted(_SUPPORTED)))
def test_supported_types_are_accepted(mime_type):
    """Property 1: each supported MIME type is accepted.

    Feature: document-audience-adapter, Property 1: Only PDF and Word source
    files are accepted.
    Validates Requirements 2.4.
    """
    assert is_supported_source_type(mime_type) is True


@pytest.mark.property
@settings(max_examples=200)
@given(mime_type=st.text().filter(lambda s: s not in _SUPPORTED))
def test_unsupported_types_are_rejected(mime_type):
    """Property 1: any string outside the supported set is rejected.

    Feature: document-audience-adapter, Property 1: Only PDF and Word source
    files are accepted.
    Validates Requirements 2.4.
    """
    assert is_supported_source_type(mime_type) is False

"""Unit tests for AdaptationRequest validation and AudienceLevel parsing.

Spec: .kiro/specs/document-audience-adapter (task 1.1)

Validates Requirement 3.1: the adapter presents exactly four AudienceLevel
values (``it_beginner``, ``intermediate_a``, ``intermediate_b``,
``opcp_expert``) and the request carries the selected level.
Validates Requirement 5.1: the AdaptationRequest references exactly one source
(either a library ``document_id`` or an ``uploaded_filename``), the audience
level, and the AI provider.
"""
import uuid

import pytest
from pydantic import ValidationError

from app.document_adapter.schemas import AdaptationRequest, AudienceLevel


# ---------------------------------------------------------------------------
# Exactly-one-of source reference (Requirement 5.1)
# ---------------------------------------------------------------------------

def test_document_id_only_is_valid():
    """A request with only ``document_id`` passes validation."""
    doc_id = uuid.uuid4()
    req = AdaptationRequest(
        document_id=doc_id,
        audience_level=AudienceLevel.IT_BEGINNER,
        ai_provider="shai",
    )

    assert req.document_id == doc_id
    assert req.uploaded_filename is None
    assert req.audience_level == AudienceLevel.IT_BEGINNER
    assert req.ai_provider == "shai"


def test_uploaded_filename_only_is_valid():
    """A request with only ``uploaded_filename`` passes validation."""
    req = AdaptationRequest(
        uploaded_filename="stored-source.pdf",
        audience_level=AudienceLevel.OPCP_EXPERT,
        ai_provider="openai",
    )

    assert req.uploaded_filename == "stored-source.pdf"
    assert req.document_id is None
    assert req.audience_level == AudienceLevel.OPCP_EXPERT


def test_both_sources_present_raises_validation_error():
    """Providing both ``document_id`` and ``uploaded_filename`` is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        AdaptationRequest(
            document_id=uuid.uuid4(),
            uploaded_filename="stored-source.pdf",
            audience_level=AudienceLevel.INTERMEDIATE_A,
            ai_provider="kiro",
        )

    assert "Exactly one of 'document_id' or 'uploaded_filename'" in str(exc_info.value)


def test_neither_source_present_raises_validation_error():
    """Providing neither source reference is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        AdaptationRequest(
            audience_level=AudienceLevel.INTERMEDIATE_B,
            ai_provider="opcp_companion",
        )

    assert "Exactly one of 'document_id' or 'uploaded_filename'" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Enum parsing for all four audience values (Requirement 3.1)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw_value",
    ["it_beginner", "intermediate_a", "intermediate_b", "opcp_expert"],
)
def test_audience_level_parses_each_value(raw_value):
    """Each of the four audience string values parses into the enum member."""
    req = AdaptationRequest(
        uploaded_filename="source.docx",
        audience_level=raw_value,
        ai_provider="shai",
    )

    assert req.audience_level == AudienceLevel(raw_value)
    assert req.audience_level.value == raw_value


def test_audience_level_enum_has_exactly_four_values_in_progression_order():
    """The enum defines exactly the four expected values in progression order."""
    assert [level.value for level in AudienceLevel] == [
        "it_beginner",
        "intermediate_a",
        "intermediate_b",
        "opcp_expert",
    ]


def test_invalid_audience_level_raises_validation_error():
    """An unknown audience string is rejected by enum parsing."""
    with pytest.raises(ValidationError):
        AdaptationRequest(
            uploaded_filename="source.pdf",
            audience_level="expert_wizard",
            ai_provider="shai",
        )


# ---------------------------------------------------------------------------
# Optional additional_context field (max 5000 characters)
# ---------------------------------------------------------------------------

def test_additional_context_defaults_to_none_when_omitted():
    """Omitting ``additional_context`` is valid and yields ``None``."""
    req = AdaptationRequest(
        uploaded_filename="source.pdf",
        audience_level=AudienceLevel.IT_BEGINNER,
        ai_provider="shai",
    )

    assert req.additional_context is None


def test_additional_context_accepts_a_normal_string():
    """A normal ``additional_context`` string is accepted verbatim."""
    req = AdaptationRequest(
        uploaded_filename="source.pdf",
        audience_level=AudienceLevel.IT_BEGINNER,
        ai_provider="shai",
        additional_context="Focus on civil engineering examples.",
    )

    assert req.additional_context == "Focus on civil engineering examples."


def test_additional_context_accepts_exactly_5000_characters():
    """An ``additional_context`` of exactly 5000 characters is accepted."""
    value = "x" * 5000
    req = AdaptationRequest(
        uploaded_filename="source.pdf",
        audience_level=AudienceLevel.IT_BEGINNER,
        ai_provider="shai",
        additional_context=value,
    )

    assert req.additional_context == value
    assert len(req.additional_context) == 5000


def test_additional_context_rejects_more_than_5000_characters():
    """An ``additional_context`` longer than 5000 characters is rejected."""
    with pytest.raises(ValidationError):
        AdaptationRequest(
            uploaded_filename="source.pdf",
            audience_level=AudienceLevel.IT_BEGINNER,
            ai_provider="shai",
            additional_context="x" * 5001,
        )

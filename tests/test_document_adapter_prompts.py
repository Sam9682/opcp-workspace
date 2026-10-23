"""Unit tests for prompt construction in the Document Audience Adapter.

Spec: .kiro/specs/document-audience-adapter (task 3.2)

Validates Requirement 3.1: the adapter maps each of the four AudienceLevel
values to an audience-specific instruction.
Validates Requirement 3.2: the built prompt reflects the selected audience
level's instruction (the progression from IT beginner to OPCP expert).

These tests cover ``build_adaptation_prompt`` together with the
``AUDIENCE_INSTRUCTIONS`` mapping and ``REWRITE_DIRECTIVE`` constant. The
source text is passed to the provider separately as ``context`` and is NOT
embedded in the returned prompt, so the tests assert the function does not
mutate its input and that distinct audience levels yield distinct prompts.
"""
import pytest

from app.document_adapter.prompts import (
    AUDIENCE_INSTRUCTIONS,
    REWRITE_DIRECTIVE,
    build_adaptation_prompt,
)
from app.document_adapter.schemas import AudienceLevel


# ---------------------------------------------------------------------------
# Each audience level yields a distinct, non-empty instruction (Requirement 3.1)
# ---------------------------------------------------------------------------

def test_every_audience_level_has_an_instruction():
    """Every AudienceLevel member maps to an instruction in the table."""
    for level in AudienceLevel:
        assert level in AUDIENCE_INSTRUCTIONS


def test_each_instruction_is_non_empty():
    """Each audience instruction is a non-empty string."""
    for level in AudienceLevel:
        instruction = AUDIENCE_INSTRUCTIONS[level]
        assert isinstance(instruction, str)
        assert instruction.strip() != ""


def test_instructions_are_distinct_across_levels():
    """No two audience levels share the same instruction text."""
    instructions = [AUDIENCE_INSTRUCTIONS[level] for level in AudienceLevel]
    assert len(set(instructions)) == len(instructions)


# ---------------------------------------------------------------------------
# The built prompt reflects the selected level (Requirement 3.2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", list(AudienceLevel))
def test_prompt_is_non_empty_for_each_level(level):
    """``build_adaptation_prompt`` returns a non-empty string for each level."""
    prompt = build_adaptation_prompt(level, "some source text")
    assert isinstance(prompt, str)
    assert prompt.strip() != ""


@pytest.mark.parametrize("level", list(AudienceLevel))
def test_prompt_contains_level_instruction_and_rewrite_directive(level):
    """The prompt embeds the selected level's instruction and the directive."""
    prompt = build_adaptation_prompt(level, "source text")
    assert AUDIENCE_INSTRUCTIONS[level] in prompt
    assert REWRITE_DIRECTIVE in prompt


def test_prompts_are_distinct_across_levels():
    """Distinct audience levels produce distinct prompts for the same source."""
    source = "identical source text"
    prompts = [build_adaptation_prompt(level, source) for level in AudienceLevel]
    assert len(set(prompts)) == len(prompts)


def test_prompt_reflects_only_the_selected_level_instruction():
    """A prompt contains its own level's instruction but not the others'."""
    for level in AudienceLevel:
        prompt = build_adaptation_prompt(level, "source text")
        for other in AudienceLevel:
            if other == level:
                continue
            assert AUDIENCE_INSTRUCTIONS[other] not in prompt


# ---------------------------------------------------------------------------
# Source text is not embedded and not mutated (task 3.2 note)
# ---------------------------------------------------------------------------

def test_source_text_is_not_embedded_in_prompt():
    """The source text is provider context, not part of the returned prompt."""
    sentinel = "UNIQUE_SOURCE_SENTINEL_12345"
    prompt = build_adaptation_prompt(AudienceLevel.IT_BEGINNER, sentinel)
    assert sentinel not in prompt


def test_source_text_is_not_mutated():
    """``build_adaptation_prompt`` leaves the input source text unchanged."""
    source = "original source content that must stay intact"
    original_copy = str(source)
    build_adaptation_prompt(AudienceLevel.INTERMEDIATE_B, source)
    assert source == original_copy


def test_prompt_is_identical_regardless_of_source_text():
    """For a fixed level, the prompt does not depend on the source text."""
    prompt_a = build_adaptation_prompt(AudienceLevel.OPCP_EXPERT, "text A")
    prompt_b = build_adaptation_prompt(AudienceLevel.OPCP_EXPERT, "a completely different text B")
    assert prompt_a == prompt_b


# ---------------------------------------------------------------------------
# Optional additional_context is appended under a heading (append-to-prompt)
# ---------------------------------------------------------------------------

from app.document_adapter.prompts import ADDITIONAL_CONTEXT_HEADING


@pytest.mark.parametrize("extra", [None, "", "   ", "\n\t "])
def test_prompt_unchanged_when_additional_context_is_empty(extra):
    """No/blank ``additional_context`` leaves the prompt byte-for-byte identical."""
    baseline = build_adaptation_prompt(AudienceLevel.IT_BEGINNER, "source text")
    with_extra = build_adaptation_prompt(
        AudienceLevel.IT_BEGINNER, "source text", extra
    )

    assert with_extra == baseline
    assert ADDITIONAL_CONTEXT_HEADING not in with_extra


def test_prompt_includes_additional_context_and_heading_when_provided():
    """A non-empty ``additional_context`` is appended under the heading."""
    extra = "Focus on civil engineering applications."
    prompt = build_adaptation_prompt(
        AudienceLevel.INTERMEDIATE_A, "source text", extra
    )

    assert ADDITIONAL_CONTEXT_HEADING in prompt
    assert extra in prompt
    # The additional context comes after the rewrite directive.
    assert prompt.index(REWRITE_DIRECTIVE) < prompt.index(extra)


def test_additional_context_is_trimmed_before_appending():
    """Surrounding whitespace is stripped from the appended context."""
    prompt = build_adaptation_prompt(
        AudienceLevel.OPCP_EXPERT, "source text", "  keep informal tone  "
    )

    assert "keep informal tone" in prompt
    assert "  keep informal tone  " not in prompt


def test_source_text_not_embedded_even_with_additional_context():
    """The source text is still provider context, not part of the prompt."""
    sentinel = "UNIQUE_SOURCE_SENTINEL_67890"
    prompt = build_adaptation_prompt(
        AudienceLevel.IT_BEGINNER, sentinel, "extra instructions"
    )

    assert sentinel not in prompt

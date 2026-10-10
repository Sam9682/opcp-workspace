"""Property-based test for Shai prompt graceful degradation.

Feature spec: .kiro/specs/shai-ia-context

Property 2: Missing or unreadable file degrades gracefully
Validates: Requirements 3.1, 3.2, 3.4

When the skill-context file is missing or unreadable, ``_load_shai_skill_context``
returns ``None``. This test drives the pure prompt builder
``_build_shai_prompt(skill_context, context, question)`` directly with
``skill_context=None`` (the value produced by that degraded path) and asserts
that the assembled prompt:

- is composed only of the existing context (when present) and the question,
- never contains a skill-context section,
- always ends with the ``Question: {question}`` block, and
- assembles without raising any error.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.oracle.ai_providers import _build_shai_prompt


# Arbitrary user questions and existing-context values. ``context`` is either
# absent (None) or a present string, matching the present/absent split the
# builder distinguishes on. We exclude the blank-line separator ("\n\n") from
# generated text so the section-count assertion is unambiguous; this does not
# narrow the behavior under test, since the builder joins parts with "\n\n".
_no_blank_line = st.text(min_size=0, max_size=200).filter(lambda s: "\n\n" not in s)
_question = _no_blank_line
_context = st.one_of(st.none(), _no_blank_line)


@given(question=_question, context=_context)
@settings(max_examples=200)
def test_missing_or_unreadable_file_degrades_gracefully(question, context):
    """With skill_context=None the prompt holds only context (if any) + question."""
    # Assembly must not raise for any generated input.
    prompt = _build_shai_prompt(None, context, question)

    # The question is always included as the final block.
    question_block = f"Question: {question}"
    assert prompt.endswith(question_block)

    if context:
        # Existing context is combined (not replaced) and precedes the question.
        context_block = f"Contexte: {context}"
        assert context_block in prompt
        assert prompt.index(context_block) < prompt.index(question_block)
        # Only the two expected blocks are present: context then question.
        assert prompt == f"{context_block}\n\n{question_block}"
    else:
        # No existing context: only the question block is present.
        assert prompt == question_block

    # No skill-context section is ever injected on the degraded path. The only
    # sections in the assembled prompt are the (optional) Contexte block and the
    # Question block.
    sections = prompt.split("\n\n")
    expected_count = 2 if context else 1
    assert len(sections) == expected_count

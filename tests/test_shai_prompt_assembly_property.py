"""Property-based tests for Shai skill-context prompt assembly (task 3.2).

Feature spec: .kiro/specs/shai-ia-context

Targets the pure function ``_build_shai_prompt(skill_context, context, question)``
in ``app.oracle.ai_providers``.

Property 1: Successful-read prompt assembly preserves order and all parts
For any non-empty skill context, any user question, and any existing context
(present or absent), when the skill context is read successfully, the assembled
prompt SHALL place the skill context before any existing context, place any
existing context before the question, include the question, and — when an
existing context is present — retain that existing context text (combine, not
replace).

Validates: Requirements 2.1, 2.2, 2.3, 2.4
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.oracle.ai_providers import _build_shai_prompt


# Non-empty skill context: must contain at least one non-whitespace char so the
# builder treats it as "present" (its `if skill_context:` guard is truthy).
non_empty_text = st.text(min_size=1).filter(lambda s: s.strip() != "")

# Existing context is present (non-empty, truthy) or absent (None). An empty
# string is falsy in the builder, so we model "present" as non-empty text.
optional_context = st.one_of(st.none(), non_empty_text)

# The question is arbitrary text (including empty), per "arbitrary question".
question_text = st.text()


@settings(max_examples=200)
@given(
    skill_context=non_empty_text,
    context=optional_context,
    question=question_text,
)
def test_successful_read_prompt_assembly_preserves_order_and_parts(
    skill_context, context, question
):
    prompt = _build_shai_prompt(skill_context, context, question)

    question_block = f"Question: {question}"

    # Reconstruct the exact expected assembly positionally rather than by
    # searching for substrings. This is fully robust even when the generated
    # skill_context / context / question contain "Question:", "Contexte:", or
    # blank-line ("\n\n") separators themselves.
    if context is not None:
        expected = "\n\n".join(
            [skill_context, f"Contexte: {context}", question_block]
        )
    else:
        expected = "\n\n".join([skill_context, question_block])

    assert prompt == expected

    # The question is always included (Req 2.2/2.4).
    assert question_block in prompt

    # Skill context is present and always first (Req 2.1/2.2).
    assert prompt.startswith(skill_context)
    skill_end = len(skill_context)
    question_start = len(expected) - len(question_block)

    if context is not None:
        # Existing context is retained (combined, not replaced) (Req 2.3): the
        # original context text appears between the skill context and question.
        context_block = f"Contexte: {context}"
        context_start = skill_end + len("\n\n")
        assert prompt[context_start:context_start + len(context_block)] == context_block
        # Order: skill context precedes existing context precedes question.
        assert skill_end <= context_start < question_start
    else:
        # No existing context section is injected (Req 2.4).
        assert prompt == skill_context + "\n\n" + question_block
        # Order: skill context precedes the question.
        assert skill_end <= question_start

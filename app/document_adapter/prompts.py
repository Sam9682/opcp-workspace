"""Prompt construction for the Document Audience Adapter feature.

Feature: document-audience-adapter
Validates Requirements 3.1, 3.2

Pure functions (no I/O) that map an :class:`AudienceLevel` to an
audience-specific instruction and build the ``question`` text sent to the AI
provider. The extracted source text is passed separately to the provider as
``context`` (see ``app/document_adapter/service.py``); it is NOT embedded in the
returned prompt, keeping these helpers side-effect free and the source text
untouched.
"""
from typing import Optional

from app.document_adapter.schemas import AudienceLevel

# Per-audience instruction describing the reader's knowledge level and the
# desired tone/depth of the rewrite. Ordered as a progression from IT beginner
# to On-Prem Cloud Platform (OPCP) expert (see design "Prompt construction").
AUDIENCE_INSTRUCTIONS: dict[AudienceLevel, str] = {
    AudienceLevel.IT_BEGINNER: (
        "Rewrite this document for an IT beginner. Explain foundational terms, "
        "avoid jargon, and define every acronym on first use. Prefer short "
        "sentences, concrete examples, and a patient, welcoming tone."
    ),
    AudienceLevel.INTERMEDIATE_A: (
        "Rewrite this document for a reader with general IT literacy. You may "
        "assume familiarity with common computing concepts, but keep any "
        "cloud and platform specifics clearly explained."
    ),
    AudienceLevel.INTERMEDIATE_B: (
        "Rewrite this document for a reader who is comfortable with cloud "
        "concepts. Focus on the On-Prem Cloud Platform (OPCP) specifics and "
        "assume general cloud familiarity so you can move faster through the "
        "basics."
    ),
    AudienceLevel.OPCP_EXPERT: (
        "Rewrite this document for an On-Prem Cloud Platform (OPCP) expert. Be "
        "concise and assume deep OPCP expertise. Emphasize edge cases, "
        "operational detail, and precise technical nuance; omit introductory "
        "explanations."
    ),
}

# Appended after the audience instruction to direct the model to rewrite the
# source text supplied as provider context.
REWRITE_DIRECTIVE = (
    "Rewrite the source document provided as context according to the "
    "instruction above. Preserve the original meaning, structure, and factual "
    "content; adapt only the language, depth, and tone to suit the target "
    "audience. Return only the rewritten document."
)

# Heading introducing optional free-text instructions supplied by the requester
# via the Document Adapter page. Appended after ``REWRITE_DIRECTIVE`` only when
# a non-empty ``additional_context`` is provided.
ADDITIONAL_CONTEXT_HEADING = (
    "Additional context from the requester (apply these instructions):"
)


def build_adaptation_prompt(
    audience: AudienceLevel,
    source_text: str,
    additional_context: Optional[str] = None,
) -> str:
    """Build the ``question`` text for an audience-tailored adaptation.

    Maps ``audience`` to its instruction and appends the rewrite directive. The
    ``source_text`` is accepted to match the provider contract but is passed to
    the provider separately as ``context`` rather than being embedded here, so
    this function performs no I/O and does not mutate ``source_text``.

    Args:
        audience: The target :class:`AudienceLevel` for the rewrite.
        source_text: The extracted source document text (passed to the provider
            as ``context``; unused in the returned prompt).
        additional_context: Optional free-text instructions supplied by the
            requester. When non-empty (after trimming), it is appended after the
            rewrite directive under :data:`ADDITIONAL_CONTEXT_HEADING`. When
            ``None`` or blank, the returned prompt is unchanged.

    Returns:
        The prompt (``question``) string combining the audience instruction, the
        rewrite directive, and (when provided) the additional context.

    Raises:
        KeyError: If ``audience`` is not a recognized :class:`AudienceLevel`.
    """
    instruction = AUDIENCE_INSTRUCTIONS[audience]
    prompt = f"{instruction}\n\n{REWRITE_DIRECTIVE}"

    extra = (additional_context or "").strip()
    if extra:
        prompt = f"{prompt}\n\n{ADDITIONAL_CONTEXT_HEADING}\n{extra}"

    return prompt

"""Pydantic schemas for the Document Audience Adapter feature.

Feature: document-audience-adapter
Validates Requirements 3.1, 5.1, 6.2
"""
import enum
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class AudienceLevel(str, enum.Enum):
    """Four fixed target audience profiles, ordered as a progression from
    IT beginner to On-Prem Cloud Platform (OPCP) expert.

    The ordering of the members encodes the progression; the backend uses the
    enum value to select the prompt instruction while the frontend supplies the
    human-readable labels.
    """
    IT_BEGINNER = "it_beginner"
    INTERMEDIATE_A = "intermediate_a"
    INTERMEDIATE_B = "intermediate_b"
    OPCP_EXPERT = "opcp_expert"


class AdaptationRequest(BaseModel):
    """Request body for ``POST /api/document-adapter/adapt``.

    Exactly one source reference must be provided: either ``document_id`` (a
    document from the existing Documents library) or ``uploaded_filename`` (the
    stored filename returned by a prior ``POST /api/documents/upload``). The
    model validator enforces this mutual exclusivity so FastAPI returns a 422
    validation error otherwise.
    """
    document_id: Optional[UUID] = Field(
        default=None,
        description="Library source document id (mutually exclusive with uploaded_filename)",
    )
    uploaded_filename: Optional[str] = Field(
        default=None,
        description="Stored filename from a prior /documents/upload (mutually exclusive with document_id)",
    )
    audience_level: AudienceLevel = Field(..., description="Target audience profile for the adaptation")
    ai_provider: Literal["shai", "kiro", "openai", "opcp_companion"] = Field(
        ..., description="AI provider used to perform the adaptation"
    )

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "AdaptationRequest":
        """Require exactly one of ``document_id`` / ``uploaded_filename``."""
        provided = [self.document_id is not None, self.uploaded_filename is not None]
        if sum(provided) != 1:
            raise ValueError(
                "Exactly one of 'document_id' or 'uploaded_filename' must be provided"
            )
        return self


class AdaptationResponse(BaseModel):
    """Response body for ``POST /api/document-adapter/adapt``."""
    adapted_content: str = Field(..., description="Source rewritten for the selected audience level")
    audience_level: AudienceLevel = Field(..., description="Audience level used for the adaptation")
    ai_provider: str = Field(..., description="AI provider that produced the adaptation")
    source_name: str = Field(..., description="Original name of the source, used for the export filename")
    processing_time: float = Field(..., description="Generation time in seconds")


class ExportRequest(BaseModel):
    """Request body for ``POST /api/document-adapter/export``."""
    adapted_content: str = Field(..., description="Adapted content to render into a downloadable file")
    source_name: str = Field(..., description="Original source name, used to build the export filename")
    audience_level: AudienceLevel = Field(..., description="Audience level, encoded into the export filename")
    format: Literal["pdf", "docx"] = Field(default="pdf", description="Export file format")

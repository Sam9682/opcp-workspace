"""Pydantic schemas for document management
Feature: OPCP-website
Validates Requirements 5.1, 5.2, 5.4
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.document import DocumentCategory, AccessLevel


class DocumentUploadRequest(BaseModel):
    """Request schema for document upload.

    The category is no longer client-supplied; the server derives it from the
    uploaded file's extension. Only the access level is provided by the client.
    """
    access_level: AccessLevel = Field(..., description="Access level for document")


class DocumentResponse(BaseModel):
    """Response schema for document information"""
    id: UUID
    filename: str
    original_name: str
    mime_type: str
    size: int
    category: DocumentCategory
    access_level: AccessLevel
    uploaded_by: UUID
    download_count: int
    created_at: datetime
    updated_at: datetime
    target_url: Optional[str] = None

    model_config = {
        "from_attributes": True
    }


class DocumentListResponse(BaseModel):
    """Response schema for document list"""
    documents: list[DocumentResponse]
    total: int


class DocumentUploadResponse(BaseModel):
    """Response schema for successful document upload"""
    success: bool
    message: str
    document: DocumentResponse



class DocumentDeleteResponse(BaseModel):
    """Response schema for document deletion"""
    success: bool
    message: str
    document_id: UUID

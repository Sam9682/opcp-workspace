"""Pydantic schemas for forum API requests and responses"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    """Schema for creating a new forum topic"""
    title: str = Field(..., min_length=1, max_length=255)


class PostCreate(BaseModel):
    """Schema for creating a new forum post"""
    content: str = Field(..., min_length=1)


class PostResponse(BaseModel):
    """Schema for forum post response"""
    id: UUID
    topic_id: UUID
    author_id: UUID
    author_name: str
    content: str
    is_hidden: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TopicResponse(BaseModel):
    """Schema for forum topic response"""
    id: UUID
    title: str
    author_id: UUID
    author_name: str
    is_pinned: bool
    is_locked: bool
    created_at: datetime
    updated_at: datetime
    post_count: int = 0
    
    class Config:
        from_attributes = True


class TopicDetailResponse(TopicResponse):
    """Schema for detailed topic response with posts"""
    posts: list[PostResponse] = []

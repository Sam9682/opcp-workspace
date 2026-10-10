"""Pydantic schemas for user data management"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class UserDataExportResponse(BaseModel):
    """Response schema for personal data export
    
    Validates Requirement 9.7:
    - Provides complete export of user's personal data
    - Includes all data categories (profile, forum, payments, events)
    - Structured in machine-readable JSON format
    """
    profile: Dict[str, Any] = Field(
        ...,
        description="User profile information including email, name, role, and membership status"
    )
    forum_topics: List[Dict[str, Any]] = Field(
        ...,
        description="List of forum topics created by the user"
    )
    forum_posts: List[Dict[str, Any]] = Field(
        ...,
        description="List of forum posts created by the user"
    )
    payments: List[Dict[str, Any]] = Field(
        ...,
        description="List of payments made by the user"
    )
    event_registrations: List[Dict[str, Any]] = Field(
        ...,
        description="List of event registrations by the user"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "profile": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "user@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                    "role": "member",
                    "is_email_verified": True,
                    "membership_expires_at": "2025-12-31T23:59:59+00:00",
                    "created_at": "2024-01-15T10:30:00+00:00",
                    "updated_at": "2024-01-15T10:30:00+00:00"
                },
                "forum_topics": [
                    {
                        "id": "223e4567-e89b-12d3-a456-426614174001",
                        "title": "Welcome to the forum",
                        "is_pinned": False,
                        "is_locked": False,
                        "created_at": "2024-01-16T14:20:00+00:00",
                        "updated_at": "2024-01-16T14:20:00+00:00"
                    }
                ],
                "forum_posts": [
                    {
                        "id": "323e4567-e89b-12d3-a456-426614174002",
                        "topic_id": "223e4567-e89b-12d3-a456-426614174001",
                        "content": "This is my first post!",
                        "is_hidden": False,
                        "created_at": "2024-01-16T14:25:00+00:00",
                        "updated_at": "2024-01-16T14:25:00+00:00"
                    }
                ],
                "payments": [
                    {
                        "id": "423e4567-e89b-12d3-a456-426614174003",
                        "amount": 50.00,
                        "currency": "EUR",
                        "payment_method": "credit_card",
                        "status": "completed",
                        "transaction_id": "pi_1234567890",
                        "invoice_url": "/storage/invoices/invoice_123.pdf",
                        "created_at": "2024-01-15T11:00:00+00:00"
                    }
                ],
                "event_registrations": [
                    {
                        "id": "523e4567-e89b-12d3-a456-426614174004",
                        "event_id": "623e4567-e89b-12d3-a456-426614174005",
                        "event_title": "Annual General Meeting",
                        "event_start_date": "2024-03-15T18:00:00+00:00",
                        "event_location": "Community Center",
                        "registered_at": "2024-01-20T09:00:00+00:00",
                        "attended": None
                    }
                ]
            }
        }


class UserDeletionResponse(BaseModel):
    """Response schema for user data deletion request
    
    Validates Requirement 9.4:
    - Confirms deletion request has been scheduled
    - Provides deletion date information
    - Complies with RGPD right to be forgotten
    """
    success: bool = Field(
        ...,
        description="Whether the deletion request was successfully scheduled"
    )
    message: str = Field(
        ...,
        description="Human-readable confirmation message"
    )
    scheduled_for: datetime = Field(
        ...,
        description="Date and time when the data will be permanently deleted"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Your account deletion has been scheduled. Your data will be permanently deleted on 2024-03-15.",
                "scheduled_for": "2024-03-15T10:30:00+00:00"
            }
        }

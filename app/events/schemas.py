"""Pydantic schemas for event management
Feature: OPCP-website
Validates Requirements 6.2
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


def _normalize_to_utc(v: datetime) -> datetime:
    """Attach UTC to a timezone-naive datetime so comparisons use an
    unambiguous, timezone-aware instant instead of the server's local clock."""
    if v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class EventCreateRequest(BaseModel):
    """Request schema for creating an event
    
    Validates Requirements 6.2:
    - Event data validation (dates, location, description)
    """
    title: str = Field(..., min_length=1, max_length=255, description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    start_date: datetime = Field(..., description="Event start date and time")
    end_date: datetime = Field(..., description="Event end date and time")
    location: Optional[str] = Field(None, max_length=255, description="Event location")
    max_participants: Optional[int] = Field(None, ge=1, description="Maximum number of participants")
    assigned_user_id: Optional[UUID] = Field(
        None,
        description=(
            "Deprecated single-user assignment. Prefer assigned_user_ids. When "
            "provided and assigned_user_ids is omitted, it is treated as a "
            "one-element assignment list."
        ),
    )
    assigned_user_ids: Optional[list[UUID]] = Field(
        None,
        description=(
            "Existing users to assign the event to (private). Empty list or "
            "null => public event visible to everyone."
        ),
    )
    
    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v: datetime) -> datetime:
        """Validate that start_date is in the future.

        A timezone-naive input is normalized to UTC for the comparison only, so
        the future check uses an unambiguous aware instant against
        datetime.now(timezone.utc) rather than the server's local clock. The
        original value is returned unchanged to preserve its tzinfo.
        """
        if _normalize_to_utc(v) <= datetime.now(timezone.utc):
            raise ValueError('Start date must be in the future.')
        return v

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v: datetime, info) -> datetime:
        """Validate that end_date is strictly after start_date.

        Both values are normalized to UTC for the comparison only, so naive and
        aware instants are compared consistently. Equal dates are disallowed.
        The original value is returned unchanged to preserve its tzinfo.
        """
        if 'start_date' in info.data and info.data['start_date'] is not None:
            if _normalize_to_utc(v) <= _normalize_to_utc(info.data['start_date']):
                raise ValueError('End date must be after start date.')
        return v


class EventUpdateRequest(BaseModel):
    """Request schema for updating an event"""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    start_date: Optional[datetime] = Field(None, description="Event start date and time")
    end_date: Optional[datetime] = Field(None, description="Event end date and time")
    location: Optional[str] = Field(None, max_length=255, description="Event location")
    max_participants: Optional[int] = Field(None, ge=1, description="Maximum number of participants")
    assigned_user_id: Optional[UUID] = Field(
        None,
        description=(
            "Deprecated single-user assignment; send an explicit null to clear. "
            "Prefer assigned_user_ids. Relies on exclude_unset in the update "
            "handler: an omitted field leaves the assignment unchanged."
        ),
    )
    assigned_user_ids: Optional[list[UUID]] = Field(
        None,
        description=(
            "Full replacement set of assigned users. Send an empty list to "
            "clear all assignments (make the event public). Omit the field to "
            "leave assignments unchanged (relies on exclude_unset)."
        ),
    )


class EventResponse(BaseModel):
    """Response schema for event data"""
    id: UUID
    title: str
    description: Optional[str]
    start_date: datetime
    end_date: datetime
    location: Optional[str]
    max_participants: Optional[int]
    created_by: UUID
    assigned_user_id: Optional[UUID] = None
    assigned_user_ids: list[UUID] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime
    participant_count: int = 0
    
    model_config = {
        "from_attributes": True
    }


class EventCreateResponse(BaseModel):
    """Response schema for event creation"""
    success: bool
    message: str
    event: EventResponse


class EventListResponse(BaseModel):
    """Response schema for event listing"""
    success: bool
    events: list[EventResponse]
    total: int
    view_format: str  # "list" or "calendar"


class EventRegistrationResponse(BaseModel):
    """Response schema for event registration"""
    success: bool
    message: str
    registration_id: Optional[UUID] = None
    participant_count: int


class EventUnregistrationResponse(BaseModel):
    """Response schema for event unregistration"""
    success: bool
    message: str
    participant_count: int


class EventCancellationResponse(BaseModel):
    """Response schema for event cancellation"""
    success: bool
    message: str
    event: EventResponse
    notifications_sent: int

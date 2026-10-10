"""Pydantic schemas for task management
Feature: manage-tasks
Mirrors app/events/schemas.py with three deltas:
- no max_participants / no registrations
- mandatory single owner_id (optional on create -> defaults to creator)
- private-by-default visibility (enforced in the router)
Validates Requirements 2.1, 2.2, 3.1, 3.4
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


class TaskCreateRequest(BaseModel):
    """Request schema for creating a task

    Validates Requirements 2.1, 2.2, 3.1, 3.4:
    - Task data validation (dates, location, description)
    - owner_id is optional here and defaults to the creator in the router
    - assigned_user_ids is an optional list of existing users
    """
    title: str = Field(..., min_length=1, max_length=255, description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    start_date: datetime = Field(..., description="Task start date and time")
    end_date: datetime = Field(..., description="Task end date and time")
    location: Optional[str] = Field(None, max_length=255, description="Task location")
    owner_id: Optional[UUID] = Field(
        None,
        description=(
            "Existing user who owns the task. Optional on create; when omitted "
            "the router defaults it to the authenticated creator."
        ),
    )
    assigned_user_ids: Optional[list[UUID]] = Field(
        None,
        description=(
            "Existing users to assign the task to. An empty list or null does "
            "NOT make the task public: tasks are private by default and remain "
            "visible only to the owner, assignees, and admins."
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


class TaskUpdateRequest(BaseModel):
    """Request schema for updating a task"""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    start_date: Optional[datetime] = Field(None, description="Task start date and time")
    end_date: Optional[datetime] = Field(None, description="Task end date and time")
    location: Optional[str] = Field(None, max_length=255, description="Task location")
    owner_id: Optional[UUID] = Field(
        None,
        description=(
            "Existing user who owns the task. Omit the field to leave the owner "
            "unchanged (relies on exclude_unset in the update handler)."
        ),
    )
    assigned_user_ids: Optional[list[UUID]] = Field(
        None,
        description=(
            "Full replacement set of assigned users. Send an empty list to "
            "clear all assignments (task stays private). Omit the field to "
            "leave assignments unchanged (relies on exclude_unset)."
        ),
    )


class TaskResponse(BaseModel):
    """Response schema for task data"""
    id: UUID
    title: str
    description: Optional[str]
    start_date: datetime
    end_date: datetime
    location: Optional[str]
    owner_id: UUID
    created_by: UUID
    assigned_user_ids: list[UUID] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class TaskCreateResponse(BaseModel):
    """Response schema for task creation"""
    success: bool
    message: str
    task: TaskResponse


class TaskListResponse(BaseModel):
    """Response schema for task listing"""
    success: bool
    tasks: list[TaskResponse]
    total: int
    view_format: str  # "list" or "calendar"


class TaskCancellationResponse(BaseModel):
    """Response schema for task cancellation"""
    success: bool
    message: str
    task: TaskResponse
    notifications_sent: int

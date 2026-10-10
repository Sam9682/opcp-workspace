"""Pydantic schemas for notification preferences endpoints"""
from pydantic import BaseModel


class NotificationPreferencesResponse(BaseModel):
    """Response schema for notification preferences
    
    Validates Requirement 10.4:
    - Returns user's notification preferences
    """
    user_id: str
    email_notifications: bool
    forum_notifications: bool
    event_notifications: bool
    announcement_notifications: bool
    
    model_config = {
        "from_attributes": True
    }


class NotificationPreferencesUpdate(BaseModel):
    """Request schema for updating notification preferences
    
    Validates Requirement 10.4:
    - Allows users to configure their notification preferences
    """
    email_notifications: bool | None = None
    forum_notifications: bool | None = None
    event_notifications: bool | None = None
    announcement_notifications: bool | None = None

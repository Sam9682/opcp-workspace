"""Pydantic schemas for administration endpoints"""
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class RoleUpdateRequest(BaseModel):
    """Request schema for updating user role
    
    Validates Requirements 7.1, 7.2:
    - Administrator can assign roles to members
    - Role must be valid (visitor, member, administrator)
    """
    role: str = Field(
        description="New role for the user",
        pattern="^(visitor|member|administrator)$"
    )


class RoleUpdateResponse(BaseModel):
    """Response schema for successful role update"""
    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    message: str = "User role updated successfully"
    
    model_config = {
        "from_attributes": True
    }


class MembershipStatusUpdateRequest(BaseModel):
    """Request schema for updating membership status
    
    Allows administrator to update membership expiration date and/or force a specific status
    """
    membership_expires_at: Optional[datetime] = Field(
        default=None,
        description="New membership expiration date (null for lifetime membership)"
    )
    membership_status: Optional[str] = Field(
        default=None,
        description="Force a specific membership status (pending, active, expired, suspended)",
        pattern="^(pending|active|expired|suspended)$"
    )


class MembershipStatusUpdateResponse(BaseModel):
    """Response schema for successful membership status update"""
    id: str
    email: str
    membership_expires_at: Optional[datetime]
    membership_status: str
    message: str = "Membership status updated successfully"
    
    model_config = {
        "from_attributes": True
    }


class EmailVerificationUpdateRequest(BaseModel):
    """Request schema for updating email verification status"""
    is_email_verified: bool = Field(
        description="Email verification status"
    )


class EmailVerificationUpdateResponse(BaseModel):
    """Response schema for successful email verification update"""
    id: str
    email: str
    is_email_verified: bool
    membership_status: str
    message: str = "Email verification status updated successfully"
    
    model_config = {
        "from_attributes": True
    }


class MemberSummary(BaseModel):
    """Summary information for a member
    
    Validates Requirements 7.3:
    - Displays all members with their roles and membership status
    """
    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    is_email_verified: bool
    membership_expires_at: Optional[datetime]
    membership_status: str  # 'active', 'expired', 'suspended'
    created_at: datetime
    
    model_config = {
        "from_attributes": True
    }


class MemberListResponse(BaseModel):
    """Response schema for member list"""
    members: list[MemberSummary]
    total: int
    
    model_config = {
        "from_attributes": True
    }


class DeactivateMemberResponse(BaseModel):
    """Response schema for member deactivation"""
    id: str
    email: str
    message: str = "Member account deactivated successfully"
    
    model_config = {
        "from_attributes": True
    }


class AuditLogEntry(BaseModel):
    """Schema for a single audit log entry
    
    Validates Requirements 7.5:
    - Displays administrative actions with timestamp and admin identity
    """
    id: str
    admin_id: Optional[str]
    admin_email: Optional[str]  # Denormalized for convenience
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    details: Optional[dict[str, Any]]
    timestamp: datetime
    
    model_config = {
        "from_attributes": True
    }


class AuditLogResponse(BaseModel):
    """Response schema for audit log listing with pagination"""
    entries: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
    
    model_config = {
        "from_attributes": True
    }


class LoginLogEntry(BaseModel):
    """A single user connection event (login / logout / failed login).

    Captures who connected (user identity), when (timestamp), the type of
    event (action), and connection metadata (IP address, user-agent).
    """
    id: str
    user_id: Optional[str]
    user_email: Optional[str]
    user_name: Optional[str]
    action: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    reason: Optional[str] = None
    timestamp: datetime

    model_config = {
        "from_attributes": True
    }


class LoginLogResponse(BaseModel):
    """Response schema for the login/connection log listing with pagination."""
    entries: list[LoginLogEntry]
    total: int
    page: int
    page_size: int

    model_config = {
        "from_attributes": True
    }


class ForumActivityStats(BaseModel):
    """Forum activity statistics"""
    topics: int = Field(description="Number of topics created in the period")
    posts: int = Field(description="Number of posts created in the period")


class ActivityReportResponse(BaseModel):
    """Response schema for activity report
    
    Validates Requirements 8.4:
    - Generates annual activity reports accessible to all members
    """
    period_start: datetime = Field(description="Start date of the reporting period")
    period_end: datetime = Field(description="End date of the reporting period")
    new_members: int = Field(description="Number of new members registered in the period")
    active_members: int = Field(description="Number of members with active membership status")
    events_held: int = Field(description="Number of events held in the period")
    forum_activity: ForumActivityStats = Field(description="Forum activity statistics")
    revenue: float = Field(description="Total revenue from payments in the period (in EUR)")
    
    model_config = {
        "from_attributes": True
    }



class AnnouncementRequest(BaseModel):
    """Request schema for sending an announcement
    
    Validates Requirement 10.5:
    - Administrator can send announcements to all active members
    """
    subject: str = Field(
        min_length=1,
        max_length=255,
        description="Announcement subject"
    )
    content: str = Field(
        min_length=1,
        description="Announcement content"
    )
    sender_name: Optional[str] = Field(
        default="OPCP",
        description="Name of the sender (defaults to OPCP)"
    )


class AnnouncementResponse(BaseModel):
    """Response schema for announcement sending"""
    success: bool
    message: str
    notifications_sent: int = Field(description="Number of notifications sent successfully")
    total_members: int = Field(description="Total number of active members")
    
    model_config = {
        "from_attributes": True
    }


class AIProviderStatus(BaseModel):
    """Enablement status for a single AI Oracle provider."""
    provider: str = Field(description="Canonical provider id (shai, kiro, openai, opcp_companion)")
    name: str = Field(description="Human-readable provider name")
    enabled: bool = Field(description="Whether the provider is offered in the AI Oracle dropdown")
    always_enabled: bool = Field(
        default=False,
        description="True when the provider cannot be disabled (e.g. shai)"
    )


class AIProviderConfigResponse(BaseModel):
    """List of AI provider enablement statuses."""
    providers: list[AIProviderStatus]


class AIProviderUpdateItem(BaseModel):
    """Requested enablement change for one provider."""
    provider: str = Field(
        description="Provider id to update",
        pattern="^(shai|kiro|openai|opcp_companion)$"
    )
    enabled: bool = Field(description="Desired enabled state")


class AIProviderConfigUpdateRequest(BaseModel):
    """Bulk update request for AI provider enablement flags."""
    providers: list[AIProviderUpdateItem] = Field(
        description="Enablement changes to apply"
    )


class ForumConfigResponse(BaseModel):
    """Forum configuration flags exposed to admins."""
    view_button_enabled: bool = Field(
        description='Whether the "View" button is displayed on the public home page'
    )


class ForumConfigUpdateRequest(BaseModel):
    """Update request for forum configuration flags."""
    view_button_enabled: bool = Field(
        description='Desired state for the "View" button on the public home page'
    )


class EncryptionConfigResponse(BaseModel):
    """Database field encryption state exposed to admins.

    Deliberately never includes the password key, verification hash, or salt.
    """
    enabled: bool = Field(
        description="Whether application-level field encryption is active for on-disk data"
    )
    key_is_set: bool = Field(
        description="Whether an administrator has set a password key"
    )


class EncryptionConfigUpdateRequest(BaseModel):
    """Update request for the database field encryption configuration.

    The password key is required to set/validate the key and to activate the
    in-memory key for the running process. The ``enabled`` field records the
    administrator's desired state; the on-disk data is only migrated to that
    state by the offline migration script.
    """
    password_key: str = Field(
        min_length=8,
        description="Symmetric password key used to derive the encryption key (never stored)"
    )
    enabled: bool = Field(
        description="Desired encryption state (applied to existing data via the migration script)"
    )

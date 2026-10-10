"""Token blacklist model for logout functionality

This model stores revoked JWT tokens to prevent their reuse after logout.
Validates Requirement 2.5: Logout terminates session.
"""

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from datetime import datetime, timezone
import uuid


class TokenBlacklist(Base):
    """Token blacklist model for storing revoked tokens
    
    When a user logs out, their JWT token is added to this blacklist
    to prevent it from being used again, even if it hasn't expired yet.
    
    Attributes:
        id: Unique identifier for the blacklist entry
        token: The JWT token string that has been revoked
        user_id: ID of the user who owned the token
        revoked_at: Timestamp when the token was revoked
        expires_at: When the token would naturally expire (for cleanup)
    """
    __tablename__ = "token_blacklist"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    def __repr__(self):
        return f"<TokenBlacklist(id={self.id}, user_id={self.user_id}, revoked_at={self.revoked_at})>"

"""Authentication dependencies for FastAPI endpoints

This module provides dependency functions for extracting and validating
JWT tokens from requests.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, TokenBlacklist
from app.auth.token import verify_token
from app.auth.schemas import ErrorResponse
from app.logging_config import logger


# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Extract and validate the current user from JWT token.
    
    This dependency extracts the JWT token from the Authorization header,
    validates it, checks if it's blacklisted, and returns the user.
    
    Args:
        credentials: HTTP Bearer token credentials
        db: Database session
        
    Returns:
        User object for the authenticated user
        
    Raises:
        HTTPException 401: If token is invalid, expired, or blacklisted
    """
    token = credentials.credentials
    
    # Check if token is blacklisted (revoked during logout)
    blacklisted = db.query(TokenBlacklist).filter(
        TokenBlacklist.token == token
    ).first()
    
    if blacklisted:
        logger.warning(f"Attempt to use blacklisted token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code="TOKEN_REVOKED",
                message="This token has been revoked. Please login again.",
                details={}
            )
        )
    
    # Verify and decode token
    payload = verify_token(token)
    if not payload:
        logger.warning(f"Invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code="INVALID_TOKEN",
                message="Invalid or expired token. Please login again.",
                details={}
            )
        )
    
    # Extract user ID from token
    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        logger.warning(f"Token missing user ID")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code="INVALID_TOKEN",
                message="Invalid token format",
                details={}
            )
        )
    
    # Convert user_id string to UUID
    try:
        from uuid import UUID
        user_uuid = UUID(user_id)
    except (ValueError, AttributeError):
        logger.warning(f"Invalid user ID format in token: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code="INVALID_TOKEN",
                message="Invalid token format",
                details={}
            )
        )
    
    # Fetch user from database
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        logger.warning(f"User not found for token: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code="USER_NOT_FOUND",
                message="User not found",
                details={}
            )
        )
    
    return user


async def get_token_from_request(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Extract the raw JWT token from the request.
    
    This is a simpler dependency that just extracts the token string
    without validating it or fetching the user.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        The JWT token string
    """
    return credentials.credentials


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Extract and validate the current user from JWT token (optional).

    This dependency is similar to get_current_user but returns None if no token
    is provided instead of raising an error. Useful for endpoints that have
    different behavior for authenticated vs unauthenticated users.

    Args:
        credentials: HTTP Bearer token credentials (optional)
        db: Database session

    Returns:
        User object for the authenticated user, or None if not authenticated

    Raises:
        HTTPException 401: If token is provided but invalid, expired, or blacklisted
    """
    if not credentials:
        return None

    token = credentials.credentials

    # Check if token is blacklisted
    blacklisted = db.query(TokenBlacklist).filter(
        TokenBlacklist.token == token
    ).first()

    if blacklisted:
        logger.warning(f"Attempt to use blacklisted token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code="TOKEN_REVOKED",
                message="This token has been revoked. Please login again.",
                details={}
            )
        )

    # Verify and decode token
    payload = verify_token(token)
    if not payload:
        logger.warning(f"Invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code="INVALID_TOKEN",
                message="Invalid or expired token. Please login again.",
                details={}
            )
        )

    # Extract user ID from token
    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        logger.warning(f"Token missing user ID")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code="INVALID_TOKEN",
                message="Invalid token format",
                details={}
            )
        )

    # Convert user_id string to UUID
    try:
        from uuid import UUID
        user_uuid = UUID(user_id)
    except (ValueError, AttributeError):
        logger.warning(f"Invalid user ID format in token: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code="INVALID_TOKEN",
                message="Invalid token format",
                details={}
            )
        )

    # Fetch user from database
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        logger.warning(f"User not found for token: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code="USER_NOT_FOUND",
                message="User not found",
                details={}
            )
        )

    return user


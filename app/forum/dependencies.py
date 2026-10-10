"""Forum access control dependencies

This module provides middleware for forum access control, ensuring that
only authenticated and verified members can access forum functionality.

Validates Requirement 3.4: Non-authenticated users are redirected to login
"""

from fastapi import Depends, HTTPException, status
from app.models import User, UserRole
from app.auth.dependencies import get_current_user
from app.auth.schemas import ErrorResponse
from app.logging_config import logger


async def get_verified_member(
    current_user: User = Depends(get_current_user)
) -> User:
    """Verify that the current user is an authenticated and verified member.
    
    This dependency ensures forum access control by checking:
    1. User is authenticated (handled by get_current_user)
    2. User's email is verified
    3. User has at least member role
    
    Args:
        current_user: The authenticated user from JWT token
        
    Returns:
        User object if all checks pass
        
    Raises:
        HTTPException 401: If email is not verified
        HTTPException 403: If user doesn't have member access
    """
    # Check if email is verified
    if not current_user.is_email_verified:
        logger.warning(
            f"Unverified user {current_user.id} attempted to access forum"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse.create(
                code="EMAIL_NOT_VERIFIED",
                message="Please verify your email address before accessing the forum",
                details={"email": current_user.email}
            )
        )
    
    # Check if user has member or administrator role
    # (VISITOR role should not have forum access)
    if current_user.role == UserRole.VISITOR:
        logger.warning(
            f"User {current_user.id} with VISITOR role attempted to access forum"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse.create(
                code="INSUFFICIENT_PERMISSIONS",
                message="Forum access requires member status",
                details={"current_role": current_user.role.value}
            )
        )
    
    logger.info(f"Forum access granted to user {current_user.id}")
    return current_user


async def get_administrator(
    current_user: User = Depends(get_current_user)
) -> User:
    """Verify that the current user is an administrator.
    
    This dependency is used for administrative forum functions like
    content moderation.
    
    Args:
        current_user: The authenticated user from JWT token
        
    Returns:
        User object if user is an administrator
        
    Raises:
        HTTPException 403: If user is not an administrator
    """
    if current_user.role != UserRole.ADMINISTRATOR:
        logger.warning(
            f"User {current_user.id} with role {current_user.role} "
            f"attempted to access admin function"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse.create(
                code="ADMIN_ACCESS_REQUIRED",
                message="This action requires administrator privileges",
                details={"current_role": current_user.role.value}
            )
        )
    
    return current_user

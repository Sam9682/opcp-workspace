"""Dependencies for event management endpoints
Feature: OPCP-website
Validates Requirements 7.2
"""
from fastapi import Depends, HTTPException, status
from app.auth.dependencies import get_current_user
from app.models import User, UserRole
from app.auth.schemas import ErrorResponse
from app.logging_config import logger


async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require that the current user has administrator role.
    
    Validates Requirements 7.2:
    - Restricts administrative functions to users with administrator role
    
    Args:
        current_user: The authenticated user
        
    Returns:
        User object if user is an administrator
        
    Raises:
        HTTPException 403: If user is not an administrator
    """
    if current_user.role != UserRole.ADMINISTRATOR:
        logger.warning(
            f"User {current_user.id} ({current_user.email}) attempted to access "
            f"admin-only endpoint without administrator role (role: {current_user.role})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse.create(
                code="INSUFFICIENT_PERMISSIONS",
                message="Administrator role required for this operation",
                details={"required_role": "administrator", "user_role": current_user.role.value}
            )
        )
    
    return current_user

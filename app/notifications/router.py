"""Notification preferences API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, NotificationPreferences
from app.auth.dependencies import get_current_user
from app.auth.schemas import ErrorResponse
from app.notifications.schemas import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate
)
from app.logging_config import logger

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Unauthorized - invalid or missing token"},
        404: {"description": "Preferences not found"}
    }
)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> NotificationPreferencesResponse:
    """Get user's notification preferences.
    
    Validates Requirement 10.4:
    - Retrieves user notification preferences
    - Creates default preferences if none exist
    
    Args:
        current_user: The authenticated user
        db: Database session
        
    Returns:
        NotificationPreferencesResponse with user's preferences
        
    Raises:
        HTTPException 401: If user is not authenticated
    """
    try:
        # Fetch user's notification preferences
        preferences = db.query(NotificationPreferences).filter(
            NotificationPreferences.user_id == current_user.id
        ).first()
        
        # If preferences don't exist, create default preferences
        if not preferences:
            logger.info(f"Creating default notification preferences for user: {current_user.email}")
            preferences = NotificationPreferences(
                user_id=current_user.id,
                email_notifications=True,
                forum_notifications=True,
                event_notifications=True,
                announcement_notifications=True
            )
            db.add(preferences)
            db.commit()
            db.refresh(preferences)
        
        logger.info(f"Retrieved notification preferences for user: {current_user.email}")
        
        return NotificationPreferencesResponse(
            user_id=str(preferences.user_id),
            email_notifications=preferences.email_notifications,
            forum_notifications=preferences.forum_notifications,
            event_notifications=preferences.event_notifications,
            announcement_notifications=preferences.announcement_notifications
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error retrieving notification preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred while retrieving notification preferences",
                details={}
            )
        )


@router.put(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Unauthorized - invalid or missing token"},
        400: {"description": "Invalid request data"}
    }
)
async def update_notification_preferences(
    preferences_update: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> NotificationPreferencesResponse:
    """Update user's notification preferences.
    
    Validates Requirement 10.4:
    - Stores user notification preferences
    - Allows users to configure which notifications they receive
    
    Args:
        preferences_update: Updated preference values
        current_user: The authenticated user
        db: Database session
        
    Returns:
        NotificationPreferencesResponse with updated preferences
        
    Raises:
        HTTPException 401: If user is not authenticated
        HTTPException 400: If request data is invalid
    """
    try:
        # Fetch existing preferences or create new ones
        preferences = db.query(NotificationPreferences).filter(
            NotificationPreferences.user_id == current_user.id
        ).first()
        
        if not preferences:
            # Create new preferences with provided values
            logger.info(f"Creating notification preferences for user: {current_user.email}")
            preferences = NotificationPreferences(
                user_id=current_user.id,
                email_notifications=preferences_update.email_notifications if preferences_update.email_notifications is not None else True,
                forum_notifications=preferences_update.forum_notifications if preferences_update.forum_notifications is not None else True,
                event_notifications=preferences_update.event_notifications if preferences_update.event_notifications is not None else True,
                announcement_notifications=preferences_update.announcement_notifications if preferences_update.announcement_notifications is not None else True
            )
            db.add(preferences)
        else:
            # Update existing preferences (only update fields that are provided)
            logger.info(f"Updating notification preferences for user: {current_user.email}")
            if preferences_update.email_notifications is not None:
                preferences.email_notifications = preferences_update.email_notifications
            if preferences_update.forum_notifications is not None:
                preferences.forum_notifications = preferences_update.forum_notifications
            if preferences_update.event_notifications is not None:
                preferences.event_notifications = preferences_update.event_notifications
            if preferences_update.announcement_notifications is not None:
                preferences.announcement_notifications = preferences_update.announcement_notifications
        
        db.commit()
        db.refresh(preferences)
        
        logger.info(f"Notification preferences updated successfully for user: {current_user.email}")
        
        return NotificationPreferencesResponse(
            user_id=str(preferences.user_id),
            email_notifications=preferences.email_notifications,
            forum_notifications=preferences.forum_notifications,
            event_notifications=preferences.event_notifications,
            announcement_notifications=preferences.announcement_notifications
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating notification preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred while updating notification preferences",
                details={}
            )
        )

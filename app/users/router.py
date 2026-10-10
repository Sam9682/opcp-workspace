"""User API endpoints for personal data management"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.models import User, Post, Topic, Payment, EventRegistration, Event, ScheduledUserDeletion
from app.auth.dependencies import get_current_user
from app.users.schemas import UserDataExportResponse, UserDeletionResponse
from app.logging_config import logger
from typing import List, Dict, Any

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get(
    "/me/export",
    response_model=UserDataExportResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Unauthorized - invalid or missing token"},
        500: {"description": "Internal server error"}
    }
)
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserDataExportResponse:
    """Export all personal data for the authenticated user.
    
    Validates Requirement 9.7:
    - Provides members with access to download their personal data
    - Generates JSON export of all user data
    - Includes profile, posts, payments, and event registrations
    - Complies with RGPD requirements for data portability
    
    Args:
        current_user: The authenticated user (from JWT token)
        db: Database session
        
    Returns:
        UserDataExportResponse with complete user data export
        
    Raises:
        HTTPException 401: If user is not authenticated
        HTTPException 500: If an error occurs during export
    """
    try:
        logger.info(f"Generating data export for user: {current_user.email} (ID: {current_user.id})")
        
        # Profile data
        profile_data = {
            "id": str(current_user.id),
            "email": current_user.email,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "role": current_user.role.value,
            "is_email_verified": current_user.is_email_verified,
            "membership_expires_at": current_user.membership_expires_at.isoformat() if current_user.membership_expires_at else None,
            "created_at": current_user.created_at.isoformat(),
            "updated_at": current_user.updated_at.isoformat()
        }
        
        # Forum topics created by user
        topics = db.query(Topic).filter(Topic.author_id == current_user.id).all()
        topics_data = [
            {
                "id": str(topic.id),
                "title": topic.title,
                "is_pinned": topic.is_pinned,
                "is_locked": topic.is_locked,
                "created_at": topic.created_at.isoformat(),
                "updated_at": topic.updated_at.isoformat()
            }
            for topic in topics
        ]
        
        # Forum posts created by user
        posts = db.query(Post).filter(Post.author_id == current_user.id).all()
        posts_data = [
            {
                "id": str(post.id),
                "topic_id": str(post.topic_id),
                "content": post.content,
                "is_hidden": post.is_hidden,
                "created_at": post.created_at.isoformat(),
                "updated_at": post.updated_at.isoformat()
            }
            for post in posts
        ]
        
        # Payments made by user
        payments = db.query(Payment).filter(Payment.user_id == current_user.id).all()
        payments_data = [
            {
                "id": str(payment.id),
                "amount": float(payment.amount),
                "currency": payment.currency,
                "payment_method": payment.payment_method.value,
                "status": payment.status.value,
                "transaction_id": payment.transaction_id,
                "invoice_url": payment.invoice_url,
                "created_at": payment.created_at.isoformat()
            }
            for payment in payments
        ]
        
        # Event registrations by user
        registrations = db.query(EventRegistration).filter(
            EventRegistration.user_id == current_user.id
        ).all()
        
        registrations_data = []
        for registration in registrations:
            # Get event details
            event = db.query(Event).filter(Event.id == registration.event_id).first()
            registrations_data.append({
                "id": str(registration.id),
                "event_id": str(registration.event_id),
                "event_title": event.title if event else None,
                "event_start_date": event.start_date.isoformat() if event else None,
                "event_location": event.location if event else None,
                "registered_at": registration.registered_at.isoformat(),
                "attended": registration.attended
            })
        
        logger.info(
            f"Data export completed for user {current_user.email}: "
            f"{len(topics_data)} topics, {len(posts_data)} posts, "
            f"{len(payments_data)} payments, {len(registrations_data)} registrations"
        )
        
        return UserDataExportResponse(
            profile=profile_data,
            forum_topics=topics_data,
            forum_posts=posts_data,
            payments=payments_data,
            event_registrations=registrations_data
        )
        
    except Exception as e:
        logger.error(f"Error generating data export for user {current_user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "EXPORT_ERROR",
                    "message": "An error occurred while generating your data export",
                    "details": {}
                }
            }
        )



@router.delete(
    "/me",
    response_model=UserDeletionResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Unauthorized - invalid or missing token"},
        409: {"description": "Conflict - deletion already scheduled"},
        500: {"description": "Internal server error"}
    }
)
async def request_account_deletion(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserDeletionResponse:
    """Request account and data deletion (RGPD right to be forgotten).
    
    Validates Requirement 9.4:
    - Schedules data deletion within 30 days
    - Anonymizes or removes personal data
    - Preserves necessary records for legal compliance
    - Complies with RGPD requirements
    
    The deletion process:
    1. Schedules deletion for 30 days from now
    2. User account is immediately deactivated (cannot login)
    3. After 30 days, personal data is anonymized/deleted
    4. Payment records are preserved for legal/financial compliance
    5. Forum posts are anonymized (author replaced with "Deleted User")
    
    Args:
        current_user: The authenticated user (from JWT token)
        db: Database session
        
    Returns:
        UserDeletionResponse with deletion schedule confirmation
        
    Raises:
        HTTPException 401: If user is not authenticated
        HTTPException 409: If deletion is already scheduled for this user
        HTTPException 500: If an error occurs during scheduling
    """
    try:
        logger.info(f"Account deletion requested by user: {current_user.email} (ID: {current_user.id})")
        
        # Check if deletion is already scheduled
        existing_deletion = db.query(ScheduledUserDeletion).filter(
            ScheduledUserDeletion.user_id == current_user.id
        ).first()
        
        if existing_deletion:
            logger.warning(
                f"Deletion already scheduled for user {current_user.email}: "
                f"scheduled_for={existing_deletion.scheduled_for}"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "DELETION_ALREADY_SCHEDULED",
                        "message": f"Account deletion is already scheduled for {existing_deletion.scheduled_for.strftime('%Y-%m-%d')}",
                        "details": {
                            "scheduled_for": existing_deletion.scheduled_for.isoformat()
                        }
                    }
                }
            )
        
        # Calculate deletion date (30 days from now)
        deletion_date = datetime.now(timezone.utc) + timedelta(days=30)
        
        # Create scheduled deletion record
        scheduled_deletion = ScheduledUserDeletion(
            user_id=current_user.id,
            user_email=current_user.email,
            user_full_name=f"{current_user.first_name} {current_user.last_name}",
            requested_at=datetime.now(timezone.utc),
            scheduled_for=deletion_date
        )
        
        db.add(scheduled_deletion)
        
        # Immediately deactivate the user account
        # Set email_verified to False to prevent login
        current_user.is_email_verified = False
        current_user.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        
        logger.info(
            f"Account deletion scheduled for user {current_user.email}: "
            f"deletion_date={deletion_date.isoformat()}"
        )
        
        return UserDeletionResponse(
            success=True,
            message=f"Your account deletion has been scheduled. Your data will be permanently deleted on {deletion_date.strftime('%Y-%m-%d')}.",
            scheduled_for=deletion_date
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error scheduling deletion for user {current_user.email}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "DELETION_SCHEDULING_ERROR",
                    "message": "An error occurred while scheduling your account deletion",
                    "details": {}
                }
            }
        )

"""Information API endpoints for PSMC information"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.models.event import Event
from app.models.forum import Topic
from app.info.schemas import (
    HomepageResponse,
    LegalInfoResponse,
    BoardInfoResponse,
    FinancialReportsResponse,
    StatsResponse
)
from app.info.config import (
    PSMC_INFO,
    MISSION,
    ACTIVITIES,
    CONTACT_EMAIL,
    CONTACT_PHONE,
    STATUTES,
    REGULATIONS,
    FINANCIAL_REPORTS,
    BOARD_LAST_UPDATED
)
from app.logging_config import logger

router = APIRouter(prefix="/api/info", tags=["information"])


@router.get(
    "/homepage",
    response_model=HomepageResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Homepage information retrieved successfully"}
    }
)
async def get_homepage_info() -> HomepageResponse:
    """Get homepage information including PSMC details, mission, and activities.
    
    Validates Requirements 1.1, 1.2, 1.4, 8.1, 8.2:
    - Returns PSMC information (name, address, board members)
    - Returns mission and activities description
    - Returns contact information
    
    This endpoint is public and does not require authentication.
    
    Returns:
        HomepageResponse with PSMC information, mission, activities, and contact details
    """
    try:
        logger.info("Homepage information requested")
        
        return HomepageResponse(
            PSMC=PSMC_INFO,
            mission=MISSION,
            activities=ACTIVITIES,
            contact_email=CONTACT_EMAIL,
            contact_phone=CONTACT_PHONE
        )
        
    except Exception as e:
        logger.error(f"Error retrieving homepage information: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An error occurred while retrieving homepage information"
            }
        )


@router.get(
    "/legal",
    response_model=LegalInfoResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Legal information retrieved successfully"}
    }
)
async def get_legal_info() -> LegalInfoResponse:
    """Get legal information including PSMC statutes and regulations.
    
    Validates Requirements 8.2, 8.3:
    - Returns PSMC statutes
    - Returns internal regulations
    
    This endpoint is public and does not require authentication, ensuring
    transparency as required for PSMCs OVH.
    
    Returns:
        LegalInfoResponse with statutes and regulations
    """
    try:
        logger.info("Legal information requested")
        
        return LegalInfoResponse(
            statutes=STATUTES,
            regulations=REGULATIONS
        )
        
    except Exception as e:
        logger.error(f"Error retrieving legal information: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An error occurred while retrieving legal information"
            }
        )


@router.get(
    "/board",
    response_model=BoardInfoResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Board information retrieved successfully"}
    }
)
async def get_board_info() -> BoardInfoResponse:
    """Get board member information.
    
    Validates Requirements 8.2:
    - Returns board member information with contact details
    - Provides transparency about PSMC leadership
    
    This endpoint is public and does not require authentication.
    
    Returns:
        BoardInfoResponse with board member details and last update date
    """
    try:
        logger.info("Board information requested")
        
        return BoardInfoResponse(
            board_members=PSMC_INFO.board_members,
            last_updated=BOARD_LAST_UPDATED
        )
        
    except Exception as e:
        logger.error(f"Error retrieving board information: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An error occurred while retrieving board information"
            }
        )


@router.get(
    "/financial-reports",
    response_model=FinancialReportsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Financial reports retrieved successfully"},
        401: {"description": "Authentication required"}
    }
)
async def get_financial_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FinancialReportsResponse:
    """Get list of financial reports accessible to members.
    
    Validates Requirements 8.5:
    - Returns list of financial reports
    - Ensures financial transparency for members
    - Requires authentication (members only)
    
    Args:
        current_user: The authenticated user (must be a member)
        db: Database session
        
    Returns:
        FinancialReportsResponse with list of available financial reports
        
    Raises:
        HTTPException 401: If user is not authenticated
    """
    try:
        logger.info(f"Financial reports requested by user: {current_user.email}")
        
        # In a real application, you might filter reports based on user role
        # or membership status, but for now we return all reports to authenticated members
        
        return FinancialReportsResponse(
            reports=FINANCIAL_REPORTS
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error retrieving financial reports: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An error occurred while retrieving financial reports"
            }
        )



@router.get(
    "/stats",
    response_model=StatsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Statistics retrieved successfully"}
    }
)
async def get_stats(db: Session = Depends(get_db)) -> StatsResponse:
    """Get public statistics about the PSMC.
    
    Returns statistics including:
    - Total number of users
    - Total number of events
    - Total number of forum topics
    
    This endpoint is public and does not require authentication.
    
    Args:
        db: Database session
        
    Returns:
        StatsResponse with PSMC statistics
    """
    try:
        logger.info("Statistics requested")
        
        # Count total users
        total_users = db.query(User).count()
        
        # Count total events
        total_events = db.query(Event).count()
        
        # Count total topics
        total_topics = db.query(Topic).count()
        
        return StatsResponse(
            total_users=total_users,
            total_events=total_events,
            total_topics=total_topics
        )
        
    except Exception as e:
        logger.error(f"Error retrieving statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An error occurred while retrieving statistics"
            }
        )

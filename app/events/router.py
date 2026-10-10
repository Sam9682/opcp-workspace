"""Event management API endpoints
Feature: OPCP-website
Validates Requirements 6.1, 6.2, 6.5, 6.7, 10.3
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, timezone
from app.database import get_db
from app.models import User, Event, EventStatus, EventRegistration, EventAssignment, NotificationPreferences, UserRole
from app.events.schemas import EventCreateRequest, EventCreateResponse, EventResponse, EventListResponse, EventRegistrationResponse, EventUnregistrationResponse, EventCancellationResponse, EventUpdateRequest
from app.events.dependencies import require_admin
from app.auth.dependencies import get_current_user
from app.services.email_service import email_service
from app.auth.schemas import ErrorResponse
from app.logging_config import logger
from icalendar import Calendar, Event as ICalEvent
from icalendar import vText


router = APIRouter(prefix="/api/events", tags=["events"])


def _validate_assigned_user(db: Session, assigned_user_id: uuid.UUID | None) -> None:
    """Validate that a non-null assigned user id references an existing user.

    Used by the create and update endpoints. Returns early when no user is
    assigned (public event). Raises 400 INVALID_ASSIGNED_USER when the id does
    not match an existing user.

    Validates Requirements 1.4, 2.3

    Args:
        db: Database session
        assigned_user_id: The assigned user id to validate, or None for a public event

    Raises:
        HTTPException 400: If assigned_user_id does not correspond to an existing user
    """
    if assigned_user_id is None:
        return
    exists = db.query(User.id).filter(User.id == assigned_user_id).first()
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_ASSIGNED_USER",
                message="Assigned user does not exist",
                details={"assigned_user_id": str(assigned_user_id)},
            ),
        )


def _validate_assigned_users(db: Session, user_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Validate a list of assigned user ids, returning a de-duplicated list.

    Every id must reference an existing user. An empty list is valid and means
    the event is public. Raises 400 INVALID_ASSIGNED_USER listing any ids that
    do not correspond to an existing user, so a bad assignment prevents the
    create/update from mutating any state.
    """
    # De-duplicate while preserving order.
    unique_ids: list[uuid.UUID] = list(dict.fromkeys(user_ids))
    if not unique_ids:
        return []

    found = {
        row[0]
        for row in db.query(User.id).filter(User.id.in_(unique_ids)).all()
    }
    missing = [uid for uid in unique_ids if uid not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_ASSIGNED_USER",
                message="One or more assigned users do not exist",
                details={"assigned_user_ids": [str(uid) for uid in missing]},
            ),
        )
    return unique_ids


def _get_assigned_user_ids(db: Session, event_id: uuid.UUID) -> list[uuid.UUID]:
    """Return the list of user ids assigned to an event (empty => public)."""
    rows = db.query(EventAssignment.user_id).filter(
        EventAssignment.event_id == event_id
    ).all()
    return [row[0] for row in rows]


def _build_event_response(db: Session, event: Event) -> EventResponse:
    """Build an EventResponse including participant count and assigned users."""
    participant_count = db.query(func.count(EventRegistration.id)).filter(
        EventRegistration.event_id == event.id
    ).scalar() or 0
    assigned_ids = _get_assigned_user_ids(db, event.id)
    return EventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        start_date=event.start_date,
        end_date=event.end_date,
        location=event.location,
        max_participants=event.max_participants,
        created_by=event.created_by,
        # Keep the legacy single-value field populated with the first assignee
        # for backward compatibility with older clients.
        assigned_user_id=assigned_ids[0] if assigned_ids else None,
        assigned_user_ids=assigned_ids,
        status=event.status.value,
        created_at=event.created_at,
        updated_at=event.updated_at,
        participant_count=participant_count,
    )


@router.post("", response_model=EventCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new event (admin only)
    
    Validates Requirements 6.2, 10.3:
    - Creates event with validated data (dates, location, description)
    - Stores event with all details
    - Sends notification to all members with event notifications enabled
    
    Args:
        event_data: Event creation data
        db: Database session
        current_user: Authenticated administrator user
        
    Returns:
        EventCreateResponse with created event details
        
    Raises:
        HTTPException 403: If user is not an administrator
        HTTPException 400: If event data is invalid
    """
    try:
        # Resolve the requested assignees. Prefer the multi-user field; fall
        # back to the deprecated single-user field when only that is provided.
        if event_data.assigned_user_ids is not None:
            requested_ids = list(event_data.assigned_user_ids)
        elif event_data.assigned_user_id is not None:
            requested_ids = [event_data.assigned_user_id]
        else:
            requested_ids = []

        # Validate all assignees before creating the event so a failure
        # prevents creation (Requirement 1.4). Empty list => public event.
        assigned_ids = _validate_assigned_users(db, requested_ids)

        # Create event. The legacy single column mirrors the first assignee for
        # backward compatibility; the join table is the source of truth.
        new_event = Event(
            title=event_data.title,
            description=event_data.description,
            start_date=event_data.start_date,
            end_date=event_data.end_date,
            location=event_data.location,
            max_participants=event_data.max_participants,
            created_by=current_user.id,
            assigned_user_id=assigned_ids[0] if assigned_ids else None,
            status=EventStatus.SCHEDULED
        )
        
        db.add(new_event)
        db.flush()  # obtain new_event.id before inserting assignment rows

        for uid in assigned_ids:
            db.add(EventAssignment(event_id=new_event.id, user_id=uid))

        db.commit()
        db.refresh(new_event)
        
        logger.info(
            f"Event created: {new_event.id} - {new_event.title} "
            f"by admin {current_user.id} ({current_user.email})"
        )
        
        # Send notifications to all members with event notifications enabled
        # Query all members (not visitors) with event notifications enabled
        members_to_notify = db.query(User).join(
            NotificationPreferences,
            User.id == NotificationPreferences.user_id,
            isouter=True
        ).filter(
            User.role.in_([UserRole.MEMBER, UserRole.ADMINISTRATOR]),
            User.is_email_verified == True,
            # If preferences exist, check event_notifications; if not, default to True
            (NotificationPreferences.event_notifications == True) | 
            (NotificationPreferences.user_id == None)
        ).all()
        
        # Send email notifications
        notification_count = 0
        for member in members_to_notify:
            # Skip the creator (they already know about the event)
            if member.id == current_user.id:
                continue
            
            # Format dates for email
            start_date_str = new_event.start_date.strftime("%d/%m/%Y à %H:%M")
            end_date_str = new_event.end_date.strftime("%d/%m/%Y à %H:%M")
            
            # Prepare email content
            subject = f"Nouvel événement OPCP : {new_event.title}"
            
            body_text = f"""
Bonjour {member.first_name},

Un nouvel événement a été créé sur OPCP :

Titre : {new_event.title}
Date de début : {start_date_str}
Date de fin : {end_date_str}
Lieu : {new_event.location or 'Non spécifié'}

{new_event.description or ''}

Connectez-vous à votre compte OPCP pour vous inscrire à cet événement.

Cordialement,
L'équipe OPCP
"""
            
            body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #1a1a1a; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f9f9f9; }}
        .event-details {{ background-color: white; padding: 15px; margin: 20px 0; border-left: 4px solid #1a1a1a; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OPCP</h1>
            <h2>Nouvel Événement</h2>
        </div>
        <div class="content">
            <p>Bonjour {member.first_name},</p>
            <p>Un nouvel événement a été créé sur OPCP :</p>
            
            <div class="event-details">
                <h3>{new_event.title}</h3>
                <p><strong>Date de début :</strong> {start_date_str}</p>
                <p><strong>Date de fin :</strong> {end_date_str}</p>
                <p><strong>Lieu :</strong> {new_event.location or 'Non spécifié'}</p>
                {f'<p><strong>Description :</strong></p><p>{new_event.description}</p>' if new_event.description else ''}
            </div>
            
            <p>Connectez-vous à votre compte OPCP pour vous inscrire à cet événement.</p>
            
            <p>Cordialement,<br>
            L'équipe OPCP</p>
        </div>
        <div class="footer">
            <p>OPCP - OVH</p>
        </div>
    </div>
</body>
</html>
"""
            
            # Send email (don't fail event creation if email fails)
            try:
                email_sent = email_service.send_email(
                    to_email=member.email,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html
                )
                if email_sent:
                    notification_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to send event notification to {member.email}: {str(e)}",
                    exc_info=True
                )
        
        logger.info(
            f"Sent {notification_count} event notifications for event {new_event.id}"
        )
        
        # Prepare response
        event_response = _build_event_response(db, new_event)
        
        return EventCreateResponse(
            success=True,
            message=f"Event created successfully. Notifications sent to {notification_count} members.",
            event=event_response
        )
    
    except HTTPException:
        # Re-raise HTTP errors (e.g. 400 INVALID_ASSIGNED_USER) unchanged so the
        # validation failure is not masked as a 500 by the generic handler.
        raise
    except ValueError as e:
        # Validation errors from Pydantic
        logger.warning(f"Event creation validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="VALIDATION_ERROR",
                message=str(e),
                details={}
            )
        )
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="EVENT_CREATION_FAILED",
                message="Failed to create event",
                details={"error": str(e)}
            )
        )


@router.get("", response_model=EventListResponse, status_code=status.HTTP_200_OK)
async def list_events(
    view: str = Query("list", pattern="^(list|calendar)$", description="View format: 'list' or 'calendar'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List upcoming events
    
    Validates Requirements 6.1, 6.5:
    - Displays all upcoming events (start_date >= current date)
    - Supports both calendar and list view formats
    - Returns same events regardless of view format (consistency)
    
    Args:
        view: View format ("list" or "calendar")
        db: Database session
        current_user: Authenticated user
        
    Returns:
        EventListResponse with list of upcoming events
        
    Raises:
        HTTPException 401: If user is not authenticated
        HTTPException 400: If view parameter is invalid
    """
    try:
        # Get current time
        now = datetime.now(timezone.utc)
        
        # Query upcoming events (start_date >= current date)
        # Only show scheduled events (not cancelled or completed)
        events_query = db.query(Event).filter(
            Event.start_date >= now,
            Event.status == EventStatus.SCHEDULED
        )

        # Role-aware visibility filtering (Requirements 3.1, 3.2, 3.3, 3.4).
        # Administrators see every upcoming scheduled event (no assignment
        # filter). Non-administrators only see public events (null assignment)
        # and events assigned to themselves; events assigned to other users are
        # excluded. Legacy rows with NULL assignment behave as public (Req 5.3).
        if current_user.role != UserRole.ADMINISTRATOR:
            # An event is visible to a non-admin when it is public (no
            # assignment rows) OR the current user is one of its assignees.
            assigned_to_me = db.query(EventAssignment.event_id).filter(
                EventAssignment.user_id == current_user.id
            )
            has_any_assignment = db.query(EventAssignment.event_id)
            events_query = events_query.filter(
                or_(
                    ~Event.id.in_(has_any_assignment),   # public: no assignees
                    Event.id.in_(assigned_to_me),        # assigned to me
                )
            )

        events_query = events_query.order_by(Event.start_date.asc())

        events = events_query.all()
        
        # Build response with participant counts and assigned users
        event_responses = [_build_event_response(db, event) for event in events]
        
        logger.info(
            f"User {current_user.id} ({current_user.email}) listed {len(event_responses)} "
            f"upcoming events in {view} view"
        )
        
        return EventListResponse(
            success=True,
            events=event_responses,
            total=len(event_responses),
            view_format=view
        )
    
    except Exception as e:
        logger.error(f"Error listing events: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="EVENT_LISTING_FAILED",
                message="Failed to retrieve events",
                details={"error": str(e)}
            )
        )



@router.post("/{event_id}/register", response_model=EventRegistrationResponse, status_code=status.HTTP_201_CREATED)
async def register_for_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Register for an event
    
    Validates Requirements 6.3:
    - Creates EventRegistration record
    - Checks max_participants limit
    - Updates participant count
    - Prevents duplicate registrations
    
    Args:
        event_id: Event UUID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        EventRegistrationResponse with registration details
        
    Raises:
        HTTPException 401: If user is not authenticated
        HTTPException 404: If event not found
        HTTPException 400: If already registered or event is full
        HTTPException 409: If event is cancelled
    """
    try:
        # Parse event_id as UUID
        try:
            event_uuid = uuid.UUID(event_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="INVALID_EVENT_ID",
                    message="Invalid event ID format",
                    details={}
                )
            )
        
        # Check if event exists
        event = db.query(Event).filter(Event.id == event_uuid).first()
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse.create(
                    code="EVENT_NOT_FOUND",
                    message="Event not found",
                    details={}
                )
            )
        
        # Check if event is cancelled
        if event.status == EventStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorResponse.create(
                    code="EVENT_CANCELLED",
                    message="Cannot register for a cancelled event",
                    details={}
                )
            )
        
        # Check if user is already registered
        existing_registration = db.query(EventRegistration).filter(
            EventRegistration.event_id == event_uuid,
            EventRegistration.user_id == current_user.id
        ).first()
        
        if existing_registration:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="ALREADY_REGISTERED",
                    message="You are already registered for this event",
                    details={}
                )
            )
        
        # Check max_participants limit
        if event.max_participants is not None:
            current_participant_count = db.query(func.count(EventRegistration.id)).filter(
                EventRegistration.event_id == event_uuid
            ).scalar() or 0
            
            if current_participant_count >= event.max_participants:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorResponse.create(
                        code="EVENT_FULL",
                        message="Event has reached maximum participant limit",
                        details={"max_participants": event.max_participants}
                    )
                )
        
        # Create registration
        new_registration = EventRegistration(
            event_id=event_uuid,
            user_id=current_user.id
        )
        
        db.add(new_registration)
        db.commit()
        db.refresh(new_registration)
        
        # Get updated participant count
        participant_count = db.query(func.count(EventRegistration.id)).filter(
            EventRegistration.event_id == event_uuid
        ).scalar() or 0
        
        logger.info(
            f"User {current_user.id} ({current_user.email}) registered for event {event_uuid} "
            f"({event.title}). Total participants: {participant_count}"
        )
        
        return EventRegistrationResponse(
            success=True,
            message="Successfully registered for event",
            registration_id=new_registration.id,
            participant_count=participant_count
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering for event: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="REGISTRATION_FAILED",
                message="Failed to register for event",
                details={"error": str(e)}
            )
        )


@router.delete("/{event_id}/register", response_model=EventUnregistrationResponse, status_code=status.HTTP_200_OK)
async def unregister_from_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Unregister from an event
    
    Validates Requirements 6.3:
    - Removes EventRegistration record
    - Updates participant count
    
    Args:
        event_id: Event UUID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        EventUnregistrationResponse with updated participant count
        
    Raises:
        HTTPException 401: If user is not authenticated
        HTTPException 404: If event not found or not registered
        HTTPException 400: If invalid event ID
    """
    try:
        # Parse event_id as UUID
        try:
            event_uuid = uuid.UUID(event_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="INVALID_EVENT_ID",
                    message="Invalid event ID format",
                    details={}
                )
            )
        
        # Check if event exists
        event = db.query(Event).filter(Event.id == event_uuid).first()
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse.create(
                    code="EVENT_NOT_FOUND",
                    message="Event not found",
                    details={}
                )
            )
        
        # Check if user is registered
        registration = db.query(EventRegistration).filter(
            EventRegistration.event_id == event_uuid,
            EventRegistration.user_id == current_user.id
        ).first()
        
        if not registration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse.create(
                    code="NOT_REGISTERED",
                    message="You are not registered for this event",
                    details={}
                )
            )
        
        # Delete registration
        db.delete(registration)
        db.commit()
        
        # Get updated participant count
        participant_count = db.query(func.count(EventRegistration.id)).filter(
            EventRegistration.event_id == event_uuid
        ).scalar() or 0
        
        logger.info(
            f"User {current_user.id} ({current_user.email}) unregistered from event {event_uuid} "
            f"({event.title}). Total participants: {participant_count}"
        )
        
        return EventUnregistrationResponse(
            success=True,
            message="Successfully unregistered from event",
            participant_count=participant_count
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unregistering from event: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="UNREGISTRATION_FAILED",
                message="Failed to unregister from event",
                details={"error": str(e)}
            )
        )



@router.put("/{event_id}", response_model=EventResponse, status_code=status.HTTP_200_OK)
async def update_event(
    event_id: str,
    event_data: EventUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update an event (admin only)"""
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_EVENT_ID",
                message="Invalid event ID format",
                details={}
            )
        )
    
    event = db.query(Event).filter(Event.id == event_uuid).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="EVENT_NOT_FOUND",
                message="Event not found",
                details={}
            )
        )
    
    try:
        if event_data.title is not None:
            event.title = event_data.title
        if event_data.description is not None:
            event.description = event_data.description
        if event_data.start_date is not None:
            event.start_date = event_data.start_date
        if event_data.end_date is not None:
            event.end_date = event_data.end_date
        if event_data.location is not None:
            event.location = event_data.location
        if event_data.max_participants is not None:
            event.max_participants = event_data.max_participants

        # Assignment set/change/clear logic (Requirements 2.1, 2.2, 2.3).
        # Use exclude_unset so an explicitly sent field is distinguished from an
        # omitted one. Presence of the key means the client intends to replace
        # the assignment set; omission leaves the current assignment unchanged.
        # assigned_user_ids (list) takes precedence over the deprecated
        # single-value assigned_user_id.
        provided = event_data.model_dump(exclude_unset=True)
        new_assignment: list[uuid.UUID] | None = None
        if "assigned_user_ids" in provided:
            ids = provided["assigned_user_ids"] or []
            new_assignment = _validate_assigned_users(db, ids)
        elif "assigned_user_id" in provided:
            single = provided["assigned_user_id"]
            new_assignment = _validate_assigned_users(db, [single] if single else [])

        if new_assignment is not None:
            # Replace the assignment set atomically: clear existing rows, then
            # insert the validated new ones. Validation ran first, so a bad id
            # aborts before any mutation.
            db.query(EventAssignment).filter(
                EventAssignment.event_id == event.id
            ).delete(synchronize_session=False)
            for uid in new_assignment:
                db.add(EventAssignment(event_id=event.id, user_id=uid))
            # Keep the legacy single column in sync with the first assignee.
            event.assigned_user_id = new_assignment[0] if new_assignment else None

        event.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(event)
    except HTTPException:
        # Re-raise HTTP errors (e.g. 400 INVALID_ASSIGNED_USER) unchanged so the
        # validation failure is not masked as a 500 by a generic handler.
        raise

    logger.info(f"Event {event.id} updated by admin {current_user.id}")
    
    return _build_event_response(db, event)


@router.put("/{event_id}/cancel", response_model=EventCancellationResponse, status_code=status.HTTP_200_OK)
async def cancel_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Cancel an event (admin only)
    
    Validates Requirements 6.6:
    - Updates event status to cancelled
    - Sends cancellation emails to all registered participants
    
    Args:
        event_id: Event UUID
        db: Database session
        current_user: Authenticated administrator user
        
    Returns:
        EventCancellationResponse with updated event and notification count
        
    Raises:
        HTTPException 403: If user is not an administrator
        HTTPException 404: If event not found
        HTTPException 400: If event is already cancelled
    """
    try:
        # Parse event_id as UUID
        try:
            event_uuid = uuid.UUID(event_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="INVALID_EVENT_ID",
                    message="Invalid event ID format",
                    details={}
                )
            )
        
        # Check if event exists
        event = db.query(Event).filter(Event.id == event_uuid).first()
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse.create(
                    code="EVENT_NOT_FOUND",
                    message="Event not found",
                    details={}
                )
            )
        
        # Check if event is already cancelled
        if event.status == EventStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="EVENT_ALREADY_CANCELLED",
                    message="Event is already cancelled",
                    details={}
                )
            )
        
        # Update event status to cancelled
        event.status = EventStatus.CANCELLED
        db.commit()
        db.refresh(event)
        
        logger.info(
            f"Event {event.id} ({event.title}) cancelled by admin {current_user.id} "
            f"({current_user.email})"
        )
        
        # Get all registered participants
        registrations = db.query(EventRegistration).filter(
            EventRegistration.event_id == event_uuid
        ).all()
        
        # Get user details for all registered participants
        participant_ids = [reg.user_id for reg in registrations]
        participants = db.query(User).filter(User.id.in_(participant_ids)).all() if participant_ids else []
        
        # Send cancellation emails to all registered participants
        notification_count = 0
        for participant in participants:
            # Format dates for email
            start_date_str = event.start_date.strftime("%d/%m/%Y à %H:%M")
            end_date_str = event.end_date.strftime("%d/%m/%Y à %H:%M")
            
            # Prepare email content
            subject = f"Annulation d'événement OPCP : {event.title}"
            
            body_text = f"""
Bonjour {participant.first_name},

Nous vous informons que l'événement suivant a été annulé :

Titre : {event.title}
Date de début : {start_date_str}
Date de fin : {end_date_str}
Lieu : {event.location or 'Non spécifié'}

{event.description or ''}

Nous nous excusons pour tout inconvénient que cela pourrait causer.

Cordialement,
L'équipe OPCP
"""
            
            body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #d32f2f; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f9f9f9; }}
        .event-details {{ background-color: white; padding: 15px; margin: 20px 0; border-left: 4px solid #d32f2f; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #888; }}
        .cancelled {{ color: #d32f2f; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>OPCP</h1>
            <h2 class="cancelled">Événement Annulé</h2>
        </div>
        <div class="content">
            <p>Bonjour {participant.first_name},</p>
            <p>Nous vous informons que l'événement suivant a été <strong class="cancelled">annulé</strong> :</p>
            
            <div class="event-details">
                <h3>{event.title}</h3>
                <p><strong>Date de début :</strong> {start_date_str}</p>
                <p><strong>Date de fin :</strong> {end_date_str}</p>
                <p><strong>Lieu :</strong> {event.location or 'Non spécifié'}</p>
                {f'<p><strong>Description :</strong></p><p>{event.description}</p>' if event.description else ''}
            </div>
            
            <p>Nous nous excusons pour tout inconvénient que cela pourrait causer.</p>
            
            <p>Cordialement,<br>
            L'équipe OPCP</p>
        </div>
        <div class="footer">
            <p>OPCP - OVH</p>
        </div>
    </div>
</body>
</html>
"""
            
            # Send email (don't fail cancellation if email fails)
            try:
                email_sent = email_service.send_email(
                    to_email=participant.email,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html
                )
                if email_sent:
                    notification_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to send cancellation notification to {participant.email}: {str(e)}",
                    exc_info=True
                )
        
        logger.info(
            f"Sent {notification_count} cancellation notifications for event {event.id} "
            f"to {len(participants)} registered participants"
        )
        
        # Prepare response (includes assigned users and participant count)
        event_response = _build_event_response(db, event)
        
        return EventCancellationResponse(
            success=True,
            message=f"Event cancelled successfully. Notifications sent to {notification_count} participants.",
            event=event_response,
            notifications_sent=notification_count
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling event: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="EVENT_CANCELLATION_FAILED",
                message="Failed to cancel event",
                details={"error": str(e)}
            )
        )



@router.get("/export/ical", status_code=status.HTTP_200_OK)
async def export_events_ical(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export events to iCal format
    
    Validates Requirements 6.7:
    - Generates valid iCal format file
    - Includes all event details (title, description, dates, location)
    - Returns file that can be imported into calendar applications
    
    Args:
        db: Database session
        current_user: Authenticated user
        
    Returns:
        iCal file with all upcoming events
        
    Raises:
        HTTPException 401: If user is not authenticated
        HTTPException 500: If iCal generation fails
    """
    try:
        # Get current time
        now = datetime.now(timezone.utc)
        
        # Query upcoming events (start_date >= current date)
        # Only show scheduled events (not cancelled or completed)
        events = db.query(Event).filter(
            Event.start_date >= now,
            Event.status == EventStatus.SCHEDULED
        ).order_by(Event.start_date.asc()).all()
        
        # Create calendar
        cal = Calendar()
        cal.add('prodid', '-//OPCP PSMC//Events Calendar//FR')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', 'OPCP Events')
        cal.add('x-wr-timezone', 'Europe/Paris')
        cal.add('x-wr-caldesc', 'Événements de l\'PSMC OPCP')
        
        # Add each event to the calendar
        for event in events:
            ical_event = ICalEvent()
            
            # Required fields
            ical_event.add('uid', f'{event.id}@OPCP.org')
            ical_event.add('dtstamp', datetime.now(timezone.utc))
            ical_event.add('dtstart', event.start_date)
            ical_event.add('dtend', event.end_date)
            ical_event.add('summary', event.title)
            
            # Optional fields
            if event.description:
                ical_event.add('description', event.description)
            
            if event.location:
                ical_event.add('location', vText(event.location))
            
            # Add status
            ical_event.add('status', 'CONFIRMED')
            
            # Add creation and modification timestamps
            ical_event.add('created', event.created_at)
            ical_event.add('last-modified', event.updated_at)
            
            # Add organizer (PSMC)
            ical_event.add('organizer', 'OPCP PSMC')
            
            # Add to calendar
            cal.add_component(ical_event)
        
        # Generate iCal content
        ical_content = cal.to_ical()
        
        logger.info(
            f"User {current_user.id} ({current_user.email}) exported {len(events)} "
            f"events to iCal format"
        )
        
        # Return as downloadable file
        return Response(
            content=ical_content,
            media_type="text/calendar",
            headers={
                "Content-Disposition": "attachment; filename=OPCP_events.ics"
            }
        )
    
    except Exception as e:
        logger.error(f"Error exporting events to iCal: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="ICAL_EXPORT_FAILED",
                message="Failed to export events to iCal format",
                details={"error": str(e)}
            )
        )

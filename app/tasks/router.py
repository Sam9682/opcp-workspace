"""Task management API endpoints
Feature: manage-tasks

Mirrors ``app/events/router.py`` but SIMPLIFIED:
- No ical export and no registration/participant endpoints.
- A mandatory single ``owner_id`` (defaults to the creator when omitted).
- Private-by-default visibility: a task is visible only to its owner, its
  assignees, and administrators. An empty assignee list does NOT make a task
  public (contrast with events).

Validates Requirements 2.3, 2.4, 2.5, 2.6, 4.1, 4.2, 4.3, 4.4, 5.1-5.4.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timezone
from app.database import get_db
from app.models import User, Task, TaskStatus, TaskAssignment, UserRole
from app.tasks.schemas import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskResponse,
    TaskListResponse,
    TaskUpdateRequest,
    TaskCancellationResponse,
)
from app.auth.dependencies import get_current_user
from app.auth.schemas import ErrorResponse
from app.logging_config import logger


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _validate_owner(db: Session, owner_id: uuid.UUID) -> uuid.UUID:
    """Validate that the owner id references an existing user.

    Owner is mandatory for a task (the router defaults it to the creator when
    the client omits it, so a value is always present here). Raises 400
    INVALID_OWNER when the id does not match an existing user, so a bad owner
    prevents the create/update from mutating any state.

    Validates Requirements 2.4, 4.4.
    """
    exists = db.query(User.id).filter(User.id == owner_id).first()
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_OWNER",
                message="Owner does not exist",
                details={"owner_id": str(owner_id)},
            ),
        )
    return owner_id


def _validate_assigned_users(db: Session, user_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Validate a list of assigned user ids, returning a de-duplicated list.

    Every id must reference an existing user. An empty list is valid and keeps
    the task private (visible only to owner + admins). Raises 400
    INVALID_ASSIGNED_USER listing any ids that do not correspond to an existing
    user, so a bad assignment prevents the create/update from mutating state.

    Validates Requirements 2.4, 4.4.
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


def _get_assigned_user_ids(db: Session, task_id: uuid.UUID) -> list[uuid.UUID]:
    """Return the list of user ids assigned to a task (may be empty)."""
    rows = db.query(TaskAssignment.user_id).filter(
        TaskAssignment.task_id == task_id
    ).all()
    return [row[0] for row in rows]


def _build_task_response(db: Session, task: Task) -> TaskResponse:
    """Build a TaskResponse with owner_id and assigned users (no participants)."""
    assigned_ids = _get_assigned_user_ids(db, task.id)
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        start_date=task.start_date,
        end_date=task.end_date,
        location=task.location,
        owner_id=task.owner_id,
        created_by=task.created_by,
        assigned_user_ids=assigned_ids,
        status=task.status.value,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _authorize_admin_owner_or_creator(current_user: User, task: Task) -> None:
    """Allow the action when the current user is admin, owner, or creator.

    Used by update and cancel to gate mutations. Raises 403 otherwise.

    Validates Requirements 4.1, 4.2, 4.3.
    """
    if current_user.role == UserRole.ADMINISTRATOR:
        return
    if task.owner_id == current_user.id or task.created_by == current_user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ErrorResponse.create(
            code="INSUFFICIENT_PERMISSIONS",
            message="You are not allowed to modify this task",
            details={},
        ),
    )


@router.post("", response_model=TaskCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new task.

    Validates Requirements 2.3, 2.4, 2.5, 2.6:
    - Persists a task with validated data.
    - Defaults ``owner_id`` to the creator when omitted (Req 2.5).
    - Rejects a non-existent owner or assignee without mutating state (Req 2.4).
    """
    try:
        # Default owner to the creator when the client omits it (Req 2.5).
        owner_id = task_data.owner_id if task_data.owner_id is not None else current_user.id
        # Validate owner and assignees BEFORE creating so a failure aborts
        # before any state mutation (Req 2.4).
        owner_id = _validate_owner(db, owner_id)
        requested_ids = list(task_data.assigned_user_ids) if task_data.assigned_user_ids else []
        assigned_ids = _validate_assigned_users(db, requested_ids)

        new_task = Task(
            title=task_data.title,
            description=task_data.description,
            start_date=task_data.start_date,
            end_date=task_data.end_date,
            location=task_data.location,
            owner_id=owner_id,
            created_by=current_user.id,
            status=TaskStatus.SCHEDULED,
        )

        db.add(new_task)
        db.flush()  # obtain new_task.id before inserting assignment rows

        for uid in assigned_ids:
            db.add(TaskAssignment(task_id=new_task.id, user_id=uid))

        db.commit()
        db.refresh(new_task)

        logger.info(
            f"Task created: {new_task.id} - {new_task.title} "
            f"by user {current_user.id} ({current_user.email})"
        )

        task_response = _build_task_response(db, new_task)
        return TaskCreateResponse(
            success=True,
            message="Task created successfully.",
            task=task_response,
        )
    except HTTPException:
        # Re-raise validation errors (e.g. 400 INVALID_OWNER) unchanged so they
        # are not masked as a 500 by the generic handler.
        raise
    except ValueError as e:
        logger.warning(f"Task creation validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="VALIDATION_ERROR",
                message=str(e),
                details={},
            ),
        )
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="TASK_CREATION_FAILED",
                message="Failed to create task",
                details={"error": str(e)},
            ),
        )


@router.get("", response_model=TaskListResponse, status_code=status.HTTP_200_OK)
async def list_tasks(
    view: str = Query("list", pattern="^(list|calendar)$", description="View format: 'list' or 'calendar'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tasks with private-by-default visibility.

    Private-by-default visibility (Requirements 5.1, 5.2, 5.3, 5.4):
    - Req 5.1: Unauthenticated requests never reach this body because the
      endpoint depends on ``get_current_user``, which rejects them.
    - Req 5.3: Administrators bypass the filter entirely and see every task.
    - Req 5.2: A non-admin sees a task only when they are its owner OR appear in
      that task's assignment rows.
    - Req 5.4: An empty assignee list does NOT make a task public. A task with
      no assignments has no rows in ``task_assignments``, so the
      ``Task.id.in_(assigned_to_me)`` subquery matches nothing for it; such a
      task is therefore visible only via the separate owner check (and to
      admins). There is no "empty means public" branch.
    """
    try:
        tasks_query = db.query(Task)

        # Private-by-default visibility filtering. Admins are exempt and see all
        # tasks (Req 5.3); everyone else is restricted to owner-or-assignee.
        if current_user.role != UserRole.ADMINISTRATOR:
            # Subquery of task ids the current user is assigned to. When the
            # user has no assignments this yields an empty set, so the ``in_``
            # below excludes every task except those the owner check keeps.
            assigned_to_me = db.query(TaskAssignment.task_id).filter(
                TaskAssignment.user_id == current_user.id
            )
            tasks_query = tasks_query.filter(
                or_(
                    Task.owner_id == current_user.id,   # tasks I own (Req 5.2)
                    Task.id.in_(assigned_to_me),        # tasks assigned to me (Req 5.2, 5.4)
                )
            )

        tasks_query = tasks_query.order_by(Task.start_date.asc())
        tasks = tasks_query.all()

        task_responses = [_build_task_response(db, task) for task in tasks]

        logger.info(
            f"User {current_user.id} ({current_user.email}) listed "
            f"{len(task_responses)} tasks in {view} view"
        )

        return TaskListResponse(
            success=True,
            tasks=task_responses,
            total=len(task_responses),
            view_format=view,
        )
    except Exception as e:
        logger.error(f"Error listing tasks: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="TASK_LISTING_FAILED",
                message="Failed to retrieve tasks",
                details={"error": str(e)},
            ),
        )


@router.put("/{task_id}", response_model=TaskResponse, status_code=status.HTTP_200_OK)
async def update_task(
    task_id: str,
    task_data: TaskUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a task.

    Validates Requirements 4.1, 4.2, 4.4:
    - Allowed for admin, owner, or creator (Req 4.1, 4.2).
    - Rejects a non-existent owner or assignee without mutating state (Req 4.4).
    """
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse.create(
                code="INVALID_TASK_ID",
                message="Invalid task ID format",
                details={},
            ),
        )

    task = db.query(Task).filter(Task.id == task_uuid).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse.create(
                code="TASK_NOT_FOUND",
                message="Task not found",
                details={},
            ),
        )

    _authorize_admin_owner_or_creator(current_user, task)

    try:
        # Use exclude_unset so an explicitly sent field is distinguished from an
        # omitted one. Validate owner and assignees BEFORE mutating, so a bad id
        # aborts before any state change (Req 4.4).
        provided = task_data.model_dump(exclude_unset=True)

        new_owner: uuid.UUID | None = None
        if "owner_id" in provided:
            owner_value = provided["owner_id"]
            if owner_value is not None:
                new_owner = _validate_owner(db, owner_value)

        new_assignment: list[uuid.UUID] | None = None
        if "assigned_user_ids" in provided:
            ids = provided["assigned_user_ids"] or []
            new_assignment = _validate_assigned_users(db, ids)

        # Apply scalar field updates only after validation succeeded.
        if task_data.title is not None:
            task.title = task_data.title
        if task_data.description is not None:
            task.description = task_data.description
        if task_data.start_date is not None:
            task.start_date = task_data.start_date
        if task_data.end_date is not None:
            task.end_date = task_data.end_date
        if task_data.location is not None:
            task.location = task_data.location
        if new_owner is not None:
            task.owner_id = new_owner

        if new_assignment is not None:
            # Replace the assignment set atomically: clear existing rows, then
            # insert the validated new ones.
            db.query(TaskAssignment).filter(
                TaskAssignment.task_id == task.id
            ).delete(synchronize_session=False)
            for uid in new_assignment:
                db.add(TaskAssignment(task_id=task.id, user_id=uid))

        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)
    except HTTPException:
        # Re-raise validation errors unchanged; nothing was committed.
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error updating task: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="TASK_UPDATE_FAILED",
                message="Failed to update task",
                details={"error": str(e)},
            ),
        )

    logger.info(f"Task {task.id} updated by user {current_user.id}")
    return _build_task_response(db, task)


@router.put("/{task_id}/cancel", response_model=TaskCancellationResponse, status_code=status.HTTP_200_OK)
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a task (soft cancel; does not hard-delete).

    Validates Requirements 4.3:
    - Allowed for admin, owner, or creator.
    - Sets status to cancelled without deleting the row.
    """
    try:
        try:
            task_uuid = uuid.UUID(task_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="INVALID_TASK_ID",
                    message="Invalid task ID format",
                    details={},
                ),
            )

        task = db.query(Task).filter(Task.id == task_uuid).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse.create(
                    code="TASK_NOT_FOUND",
                    message="Task not found",
                    details={},
                ),
            )

        _authorize_admin_owner_or_creator(current_user, task)

        if task.status == TaskStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse.create(
                    code="TASK_ALREADY_CANCELLED",
                    message="Task is already cancelled",
                    details={},
                ),
            )

        task.status = TaskStatus.CANCELLED
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)

        logger.info(
            f"Task {task.id} ({task.title}) cancelled by user {current_user.id} "
            f"({current_user.email})"
        )

        task_response = _build_task_response(db, task)
        return TaskCancellationResponse(
            success=True,
            message="Task cancelled successfully.",
            task=task_response,
            notifications_sent=0,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse.create(
                code="TASK_CANCELLATION_FAILED",
                message="Failed to cancel task",
                details={"error": str(e)},
            ),
        )

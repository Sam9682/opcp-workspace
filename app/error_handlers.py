"""Global exception handlers for FastAPI application.

This module provides consistent error response formatting for all exceptions.
Validates Requirements: All requirements (error handling)
"""

from datetime import datetime, timezone
from typing import Union
import uuid
import traceback

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from pydantic import ValidationError as PydanticValidationError

from app.exceptions import (
    OPCPException,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    ServerError
)
from app.logging_config import logger


def create_error_response(
    code: str,
    message: str,
    status_code: int,
    details: dict = None,
    request_id: str = None
) -> JSONResponse:
    """Create a standardized error response.
    
    Args:
        code: Machine-readable error code
        message: Human-readable error message
        status_code: HTTP status code
        details: Optional additional error details
        request_id: Optional request ID for tracking
        
    Returns:
        JSONResponse with standardized error format
    """
    error_response = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "requestId": request_id or str(uuid.uuid4())
        }
    }
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


async def OPCP_exception_handler(
    request: Request,
    exc: OPCPException
) -> JSONResponse:
    """Handle custom OPCP exceptions.
    
    Args:
        request: The FastAPI request object
        exc: The custom exception
        
    Returns:
        JSONResponse with error details
    """
    # Log the error
    logger.warning(
        f"OPCP exception: {exc.code} - {exc.message}",
        extra={
            "code": exc.code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return create_error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details
    )


async def validation_exception_handler(
    request: Request,
    exc: Union[RequestValidationError, PydanticValidationError]
) -> JSONResponse:
    """Handle Pydantic validation errors.
    
    Args:
        request: The FastAPI request object
        exc: The validation exception
        
    Returns:
        JSONResponse with validation error details
    """
    # Extract validation errors
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    # Log the validation error at WARNING level so a create/validation failure
    # (e.g. a 422/400 on event creation) is diagnosable server-side and never
    # silent. Include the route/path, field, and message for each error.
    error_summary = "; ".join(
        f"{err['field']}: {err['message']}" for err in errors
    ) or "no field details"
    logger.warning(
        f"Validation error on {request.method} {request.url.path} - {error_summary}",
        extra={
            "errors": errors,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    return create_error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=status.HTTP_400_BAD_REQUEST,
        details={"errors": errors}
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions.
    
    Args:
        request: The FastAPI request object
        exc: The exception
        
    Returns:
        JSONResponse with generic error message
    """
    # Log the full exception with traceback
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc()
        }
    )
    
    # Don't expose internal error details to clients
    return create_error_response(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred. Please try again later.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


async def http_exception_handler(
    request: Request,
    exc
) -> JSONResponse:
    """Handle FastAPI HTTPException with ErrorResponse format.
    
    This handler unwraps the detail field if it contains an ErrorResponse format.
    
    Args:
        request: The FastAPI request object
        exc: The HTTPException
        
    Returns:
        JSONResponse with error details
    """
    # Check if detail is already in ErrorResponse format
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        # Already in correct format, return as-is
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    # Otherwise, wrap in standard format
    return create_error_response(
        code="HTTP_ERROR",
        message=str(exc.detail) if exc.detail else "An error occurred",
        status_code=exc.status_code
    )


def register_exception_handlers(app):
    """Register all exception handlers with the FastAPI application.
    
    Args:
        app: The FastAPI application instance
    """
    # Register HTTPException handler first (most specific)
    app.add_exception_handler(HTTPException, http_exception_handler)
    
    # Register custom exception handlers
    app.add_exception_handler(OPCPException, OPCP_exception_handler)
    app.add_exception_handler(ValidationError, OPCP_exception_handler)
    app.add_exception_handler(AuthenticationError, OPCP_exception_handler)
    app.add_exception_handler(AuthorizationError, OPCP_exception_handler)
    app.add_exception_handler(NotFoundError, OPCP_exception_handler)
    app.add_exception_handler(ConflictError, OPCP_exception_handler)
    app.add_exception_handler(ServerError, OPCP_exception_handler)
    
    # Register Pydantic validation error handler
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(PydanticValidationError, validation_exception_handler)
    
    # Register generic exception handler for unexpected errors
    app.add_exception_handler(Exception, generic_exception_handler)

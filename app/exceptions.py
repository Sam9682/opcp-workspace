"""Custom exception classes for the OPCP application.

This module defines custom exceptions for consistent error handling across the application.
Validates Requirements: All requirements (error handling)
"""

from typing import Optional, Dict, Any


class OPCPException(Exception):
    """Base exception class for all OPCP exceptions."""
    
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            code: Machine-readable error code
            status_code: HTTP status code
            details: Optional additional error details
        """
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(OPCPException):
    """Exception raised for validation errors (400 Bad Request)."""
    
    def __init__(
        self,
        message: str = "Validation error",
        code: str = "VALIDATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, 400, details)


class AuthenticationError(OPCPException):
    """Exception raised for authentication errors (401 Unauthorized)."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        code: str = "AUTHENTICATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, 401, details)


class AuthorizationError(OPCPException):
    """Exception raised for authorization errors (403 Forbidden)."""
    
    def __init__(
        self,
        message: str = "Access forbidden",
        code: str = "AUTHORIZATION_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, 403, details)


class NotFoundError(OPCPException):
    """Exception raised when a resource is not found (404 Not Found)."""
    
    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "NOT_FOUND",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, 404, details)


class ConflictError(OPCPException):
    """Exception raised for conflict errors (409 Conflict)."""
    
    def __init__(
        self,
        message: str = "Resource conflict",
        code: str = "CONFLICT_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, 409, details)


class ServerError(OPCPException):
    """Exception raised for internal server errors (500 Internal Server Error)."""
    
    def __init__(
        self,
        message: str = "Internal server error",
        code: str = "SERVER_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code, 500, details)

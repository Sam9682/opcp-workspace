"""Rate limiting middleware for the OPCP website.

This module provides rate limiting functionality using slowapi to prevent
abuse and brute-force attacks on sensitive endpoints.

Requirements: 2.4, 9.6
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def get_identifier(request: Request) -> str:
    """Get identifier for rate limiting.
    
    Uses the client's IP address as the primary identifier.
    For authentication endpoints, the email from the request body
    can be used as an additional identifier.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address as identifier
    """
    return get_remote_address(request)


# Create limiter instance
# This will be used to decorate endpoints with rate limits
limiter = Limiter(
    key_func=get_identifier,
    default_limits=["100/minute"],  # Default limit for all endpoints
    storage_uri="memory://",  # In-memory storage (use Redis for production)
    headers_enabled=False  # Disable header injection to avoid response parameter requirement
)

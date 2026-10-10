"""Rate limiting for authentication endpoints.

This module provides rate limiting functionality to prevent brute-force attacks,
as required by Requirement 9.6 and the design document's error handling section.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
from collections import defaultdict


class RateLimiter:
    """Simple in-memory rate limiter for authentication attempts.
    
    Note: This is a basic implementation suitable for single-server deployments.
    For production with multiple servers, consider using Redis-based rate limiting.
    """
    
    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        """Initialize rate limiter.
        
        Args:
            max_attempts: Maximum number of attempts allowed in the time window
            window_minutes: Time window in minutes
        """
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        # Store attempts as: {identifier: [(timestamp1, timestamp2, ...)]}
        self._attempts: Dict[str, list] = defaultdict(list)
    
    def is_rate_limited(self, identifier: str) -> Tuple[bool, int]:
        """Check if an identifier is rate limited.
        
        Args:
            identifier: Unique identifier (e.g., email address or IP)
            
        Returns:
            Tuple of (is_limited, remaining_attempts)
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=self.window_minutes)
        
        # Get attempts for this identifier
        attempts = self._attempts[identifier]
        
        # Remove attempts outside the time window
        attempts = [ts for ts in attempts if ts > window_start]
        self._attempts[identifier] = attempts
        
        # Check if rate limited
        is_limited = len(attempts) >= self.max_attempts
        remaining = max(0, self.max_attempts - len(attempts))
        
        return is_limited, remaining
    
    def record_attempt(self, identifier: str) -> None:
        """Record an authentication attempt.
        
        Args:
            identifier: Unique identifier (e.g., email address or IP)
        """
        now = datetime.now(timezone.utc)
        self._attempts[identifier].append(now)
    
    def reset(self, identifier: str) -> None:
        """Reset attempts for an identifier (e.g., after successful login).
        
        Args:
            identifier: Unique identifier to reset
        """
        if identifier in self._attempts:
            del self._attempts[identifier]
    
    def cleanup_old_entries(self) -> None:
        """Remove old entries to prevent memory growth.
        
        Should be called periodically in production.
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=self.window_minutes)
        
        # Remove identifiers with no recent attempts
        identifiers_to_remove = []
        for identifier, attempts in self._attempts.items():
            # Filter out old attempts
            recent_attempts = [ts for ts in attempts if ts > window_start]
            if not recent_attempts:
                identifiers_to_remove.append(identifier)
            else:
                self._attempts[identifier] = recent_attempts
        
        for identifier in identifiers_to_remove:
            del self._attempts[identifier]


# Global rate limiter instance
# 5 attempts per 15 minutes as specified in the design document
login_rate_limiter = RateLimiter(max_attempts=5, window_minutes=15)

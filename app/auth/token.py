"""JWT token service for authentication.

This module provides JWT token generation and validation for user authentication,
as required by Requirements 2.3, 2.5, and 9.5.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from app.config import settings


class TokenService:
    """Service for generating and validating JWT tokens."""
    
    def __init__(self):
        """Initialize the token service with configuration from settings."""
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    
    def create_access_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Generate a JWT access token.
        
        Args:
            data: Dictionary of claims to encode in the token (e.g., {"sub": user_id})
            expires_delta: Optional custom expiration time. If not provided,
                          uses ACCESS_TOKEN_EXPIRE_MINUTES from settings (30 minutes)
        
        Returns:
            Encoded JWT token string
            
        Example:
            >>> token_service = TokenService()
            >>> token = token_service.create_access_token({"sub": "user123"})
            >>> print(token)
            eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        """
        to_encode = data.copy()
        
        # Set expiration time
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=self.access_token_expire_minutes
            )
        
        # Add standard JWT claims
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc)
        })
        
        # Encode and return token
        encoded_jwt = jwt.encode(
            to_encode, 
            self.secret_key, 
            algorithm=self.algorithm
        )
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token.
        
        Args:
            token: The JWT token string to verify
            
        Returns:
            Dictionary of decoded claims if token is valid, None otherwise
            
        Raises:
            None - returns None for any verification failure
            
        Example:
            >>> token_service = TokenService()
            >>> token = token_service.create_access_token({"sub": "user123"})
            >>> payload = token_service.verify_token(token)
            >>> print(payload["sub"])
            user123
        """
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            # Token has expired (session timeout - Requirement 9.5)
            return None
        except jwt.InvalidTokenError:
            # Token is invalid (malformed, wrong signature, etc.)
            return None
        except Exception:
            # Any other error
            return None


# Global token service instance
token_service = TokenService()


def create_access_token(
    data: Dict[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """Convenience function to create an access token.
    
    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    return token_service.create_access_token(data, expires_delta)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Convenience function to verify a token.
    
    Args:
        token: The JWT token string to verify
        
    Returns:
        Dictionary of decoded claims if valid, None otherwise
    """
    return token_service.verify_token(token)

"""Unit tests for JWT token service.

Tests the TokenService class and its methods for generating and validating
JWT tokens as required by Requirements 2.3, 2.5, and 9.5.
"""

import pytest
from datetime import timedelta, datetime, timezone
import time
import jwt
from app.auth.token import TokenService, create_access_token, verify_token
from app.config import settings


class TestTokenService:
    """Test suite for JWT token service functionality."""
    
    def test_create_access_token_returns_valid_jwt(self):
        """Test that create_access_token returns a valid JWT token."""
        token_service = TokenService()
        data = {"sub": "user123", "email": "test@example.com"}
        
        token = token_service.create_access_token(data)
        
        # Token should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Token should have three parts separated by dots (JWT format)
        parts = token.split(".")
        assert len(parts) == 3
    
    def test_create_access_token_includes_claims(self):
        """Test that created token includes the provided claims."""
        token_service = TokenService()
        data = {"sub": "user123", "email": "test@example.com", "role": "member"}
        
        token = token_service.create_access_token(data)
        payload = token_service.verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "member"
    
    def test_create_access_token_includes_expiration(self):
        """Test that created token includes expiration claim."""
        token_service = TokenService()
        data = {"sub": "user123"}
        
        token = token_service.create_access_token(data)
        payload = token_service.verify_token(token)
        
        assert payload is not None
        assert "exp" in payload
        assert "iat" in payload
        
        # Expiration should be in the future
        exp_timestamp = payload["exp"]
        assert exp_timestamp > datetime.now(timezone.utc).timestamp()
    
    def test_create_access_token_default_expiration(self):
        """Test that default expiration is 30 minutes as per Requirement 9.5."""
        token_service = TokenService()
        data = {"sub": "user123"}
        
        before_creation = datetime.now(timezone.utc)
        token = token_service.create_access_token(data)
        after_creation = datetime.now(timezone.utc)
        
        payload = token_service.verify_token(token)
        assert payload is not None
        
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        
        # Expiration should be approximately 30 minutes from creation
        expected_exp = iat_time + timedelta(minutes=30)
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 2  # Allow 2 seconds tolerance
    
    def test_create_access_token_custom_expiration(self):
        """Test that custom expiration time is respected."""
        token_service = TokenService()
        data = {"sub": "user123"}
        custom_delta = timedelta(minutes=5)
        
        token = token_service.create_access_token(data, expires_delta=custom_delta)
        payload = token_service.verify_token(token)
        
        assert payload is not None
        
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        
        # Expiration should be approximately 5 minutes from creation
        expected_exp = iat_time + timedelta(minutes=5)
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 2  # Allow 2 seconds tolerance
    
    def test_verify_token_with_valid_token(self):
        """Test that verify_token returns payload for valid token."""
        token_service = TokenService()
        data = {"sub": "user123", "email": "test@example.com"}
        
        token = token_service.create_access_token(data)
        payload = token_service.verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
    
    def test_verify_token_with_expired_token(self):
        """Test that verify_token returns None for expired token (Requirement 9.5)."""
        token_service = TokenService()
        data = {"sub": "user123"}
        
        # Create token that expires immediately
        token = token_service.create_access_token(
            data, 
            expires_delta=timedelta(seconds=1)
        )
        
        # Wait for token to expire
        time.sleep(2)
        
        payload = token_service.verify_token(token)
        assert payload is None
    
    def test_verify_token_with_invalid_token(self):
        """Test that verify_token returns None for invalid token."""
        token_service = TokenService()
        
        invalid_token = "invalid.token.string"
        payload = token_service.verify_token(invalid_token)
        
        assert payload is None
    
    def test_verify_token_with_malformed_token(self):
        """Test that verify_token handles malformed tokens gracefully."""
        token_service = TokenService()
        
        malformed_tokens = [
            "not_a_jwt",
            "only.two.parts",
            "",
            "a.b.c.d.e",  # Too many parts
        ]
        
        for malformed_token in malformed_tokens:
            payload = token_service.verify_token(malformed_token)
            assert payload is None
    
    def test_verify_token_with_wrong_signature(self):
        """Test that verify_token rejects tokens with wrong signature."""
        token_service = TokenService()
        data = {"sub": "user123"}
        
        # Create token with different secret
        wrong_token = jwt.encode(
            {
                **data,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
                "iat": datetime.now(timezone.utc)
            },
            "wrong_secret_key",
            algorithm="HS256"
        )
        
        payload = token_service.verify_token(wrong_token)
        assert payload is None
    
    def test_verify_token_with_wrong_algorithm(self):
        """Test that verify_token rejects tokens with wrong algorithm."""
        token_service = TokenService()
        data = {"sub": "user123"}
        
        # Create token with different algorithm
        wrong_token = jwt.encode(
            {
                **data,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
                "iat": datetime.now(timezone.utc)
            },
            settings.SECRET_KEY,
            algorithm="HS512"  # Different algorithm
        )
        
        payload = token_service.verify_token(wrong_token)
        assert payload is None
    
    def test_create_access_token_does_not_modify_input(self):
        """Test that create_access_token doesn't modify the input data dict."""
        token_service = TokenService()
        original_data = {"sub": "user123", "email": "test@example.com"}
        data_copy = original_data.copy()
        
        token_service.create_access_token(original_data)
        
        # Original data should be unchanged
        assert original_data == data_copy
        assert "exp" not in original_data
        assert "iat" not in original_data
    
    def test_multiple_tokens_are_different(self):
        """Test that creating multiple tokens with same data produces different tokens.
        
        This is expected because the 'iat' (issued at) timestamp will be different.
        Note: If tokens are created within the same second, they may be identical.
        """
        token_service = TokenService()
        data = {"sub": "user123"}
        
        token1 = token_service.create_access_token(data)
        time.sleep(1.1)  # Wait over 1 second to ensure different timestamp
        token2 = token_service.create_access_token(data)
        
        # Tokens should be different due to different 'iat' timestamps
        assert token1 != token2
        
        # But both should be valid and contain the same user data
        payload1 = token_service.verify_token(token1)
        payload2 = token_service.verify_token(token2)
        
        assert payload1 is not None
        assert payload2 is not None
        assert payload1["sub"] == payload2["sub"]
    
    def test_token_with_empty_data(self):
        """Test creating and verifying token with empty data dict."""
        token_service = TokenService()
        data = {}
        
        token = token_service.create_access_token(data)
        payload = token_service.verify_token(token)
        
        assert payload is not None
        assert "exp" in payload
        assert "iat" in payload
    
    def test_token_with_various_data_types(self):
        """Test that tokens can contain various data types."""
        token_service = TokenService()
        data = {
            "sub": "user123",
            "email": "test@example.com",
            "role": "member",
            "is_verified": True,
            "login_count": 42,
            "permissions": ["read", "write"]
        }
        
        token = token_service.create_access_token(data)
        payload = token_service.verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "member"
        assert payload["is_verified"] is True
        assert payload["login_count"] == 42
        assert payload["permissions"] == ["read", "write"]


class TestConvenienceFunctions:
    """Test suite for convenience functions."""
    
    def test_create_access_token_function(self):
        """Test the convenience create_access_token function."""
        data = {"sub": "user123"}
        
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_token_function(self):
        """Test the convenience verify_token function."""
        data = {"sub": "user123", "email": "test@example.com"}
        
        token = create_access_token(data)
        payload = verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
    
    def test_convenience_functions_work_together(self):
        """Test that convenience functions work together correctly."""
        data = {"sub": "user123", "role": "administrator"}
        
        # Create token with convenience function
        token = create_access_token(data)
        
        # Verify with convenience function
        payload = verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["role"] == "administrator"

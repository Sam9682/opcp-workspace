"""Unit tests for password hashing utilities.

Tests the hash_password() and verify_password() functions to ensure
secure password storage as required by Requirement 9.1.
"""

import pytest
from app.auth.password import hash_password, verify_password


class TestPasswordHashing:
    """Test suite for password hashing functionality."""

    def test_hash_password_returns_different_hash_each_time(self):
        """Test that hashing the same password twice produces different hashes.
        
        This verifies that bcrypt is using a unique salt for each hash.
        """
        password = "TestPassword123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2
        assert hash1.startswith("$2b$")  # bcrypt hash format
        assert hash2.startswith("$2b$")

    def test_verify_password_with_correct_password(self):
        """Test that verify_password returns True for correct password."""
        password = "MySecurePass123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True

    def test_verify_password_with_incorrect_password(self):
        """Test that verify_password returns False for incorrect password."""
        password = "MySecurePass123"
        hashed = hash_password(password)
        
        assert verify_password("WrongPassword", hashed) is False

    def test_verify_password_case_sensitive(self):
        """Test that password verification is case-sensitive."""
        password = "MySecurePass123"
        hashed = hash_password(password)
        
        assert verify_password("mysecurepass123", hashed) is False
        assert verify_password("MYSECUREPASS123", hashed) is False

    def test_hash_password_with_special_characters(self):
        """Test hashing passwords with special characters."""
        password = "P@ssw0rd!#$%^&*()"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True

    def test_hash_password_with_unicode_characters(self):
        """Test hashing passwords with unicode characters."""
        password = "Pässwörd123éñ"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True

    def test_hash_password_with_empty_string(self):
        """Test hashing an empty password (edge case)."""
        password = ""
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
        assert verify_password("a", hashed) is False

    def test_hash_password_with_long_password(self):
        """Test hashing a very long password.
        
        Note: bcrypt has a 72-byte limit. Passwords longer than 72 bytes
        should be truncated or pre-hashed before bcrypt hashing.
        """
        # Test with a password at the limit (72 bytes)
        password = "a" * 72
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
        
        # Test that passwords longer than 72 bytes raise an error
        # This is expected behavior - applications should validate
        # password length before hashing
        very_long_password = "a" * 100
        with pytest.raises(ValueError, match="password cannot be longer than 72 bytes"):
            hash_password(very_long_password)

    def test_verify_password_with_invalid_hash_format(self):
        """Test that verify_password handles invalid hash format gracefully."""
        password = "TestPassword123"
        invalid_hash = "not_a_valid_hash"
        
        # bcrypt should return False for invalid hash format
        assert verify_password(password, invalid_hash) is False

    def test_hash_format_is_bcrypt(self):
        """Test that the hash format is bcrypt ($2b$ prefix)."""
        password = "TestPassword123"
        hashed = hash_password(password)
        
        # bcrypt hashes start with $2b$ (or $2a$, $2y$ for older versions)
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$") or hashed.startswith("$2y$")
        # bcrypt hashes are typically 60 characters long
        assert len(hashed) == 60

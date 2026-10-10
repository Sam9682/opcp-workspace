"""Password hashing utilities using bcrypt.

This module provides secure password hashing and verification functions
using the bcrypt algorithm, as required by Requirement 9.1.
"""

import bcrypt

# bcrypt is an industry-standard hashing algorithm that is:
# - Slow by design (resistant to brute-force attacks)
# - Includes automatic salt generation
# - Adaptive (can increase rounds as hardware improves)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.
    
    Args:
        password: The plain text password to hash
        
    Returns:
        The hashed password string
        
    Raises:
        ValueError: If password is longer than 72 bytes (bcrypt limit)
        
    Example:
        >>> hashed = hash_password("MySecurePass123")
        >>> print(hashed)
        $2b$12$...
    """
    # Convert password to bytes and generate hash
    password_bytes = password.encode('utf-8')
    
    # bcrypt has a 72-byte limit - validate before hashing
    if len(password_bytes) > 72:
        raise ValueError("password cannot be longer than 72 bytes")
    
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Return as string for storage
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to compare against
        
    Returns:
        True if the password matches the hash, False otherwise
        
    Example:
        >>> hashed = hash_password("MySecurePass123")
        >>> verify_password("MySecurePass123", hashed)
        True
        >>> verify_password("WrongPassword", hashed)
        False
    """
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except (ValueError, AttributeError):
        # Invalid hash format or other error
        return False

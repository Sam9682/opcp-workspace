"""Unit tests for user registration endpoint

Tests Requirements 2.1, 2.2, 2.7:
- Valid registration creates account
- Duplicate email rejection
- Password complexity enforcement
"""
import pytest
from fastapi import status
from app.models import User, UserRole


def test_register_valid_user(client, db_session):
    """Test successful user registration with valid data
    
    Validates Requirement 2.1: Valid registration creates account
    """
    registration_data = {
        "email": "newuser@example.com",
        "password": "SecurePass123",
        "first_name": "John",
        "last_name": "Doe"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == registration_data["email"]
    assert data["first_name"] == registration_data["first_name"]
    assert data["last_name"] == registration_data["last_name"]
    assert "id" in data
    assert "message" in data
    
    # Verify user was created in database
    user = db_session.query(User).filter(User.email == registration_data["email"]).first()
    assert user is not None
    assert user.email == registration_data["email"]
    assert user.first_name == registration_data["first_name"]
    assert user.last_name == registration_data["last_name"]
    assert user.role == UserRole.MEMBER
    assert user.is_email_verified is False  # Should be unverified initially


def test_register_duplicate_email(client, test_user):
    """Test registration rejection with duplicate email
    
    Validates Requirement 2.2: Duplicate email rejection
    """
    registration_data = {
        "email": test_user.email,  # Use existing user's email
        "password": "DifferentPass123",
        "first_name": "Jane",
        "last_name": "Smith"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    
    assert response.status_code == status.HTTP_409_CONFLICT
    data = response.json()
    assert "detail" in data
    error = data["detail"]["error"]
    assert error["code"] == "EMAIL_ALREADY_EXISTS"
    assert "already exists" in error["message"].lower()


def test_register_password_too_short(client):
    """Test password complexity: minimum 8 characters
    
    Validates Requirement 2.7: Password complexity enforcement
    """
    registration_data = {
        "email": "test@example.com",
        "password": "Short1",  # Only 6 characters
        "first_name": "John",
        "last_name": "Doe"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "detail" in data


def test_register_password_no_uppercase(client):
    """Test password complexity: requires uppercase letter
    
    Validates Requirement 2.7: Password complexity enforcement
    """
    registration_data = {
        "email": "test@example.com",
        "password": "lowercase123",  # No uppercase
        "first_name": "John",
        "last_name": "Doe"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "detail" in data
    # Check that error mentions uppercase requirement
    error_msg = str(data["detail"]).lower()
    assert "uppercase" in error_msg


def test_register_password_no_lowercase(client):
    """Test password complexity: requires lowercase letter
    
    Validates Requirement 2.7: Password complexity enforcement
    """
    registration_data = {
        "email": "test@example.com",
        "password": "UPPERCASE123",  # No lowercase
        "first_name": "John",
        "last_name": "Doe"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "detail" in data
    error_msg = str(data["detail"]).lower()
    assert "lowercase" in error_msg


def test_register_password_no_number(client):
    """Test password complexity: requires number
    
    Validates Requirement 2.7: Password complexity enforcement
    """
    registration_data = {
        "email": "test@example.com",
        "password": "NoNumbersHere",  # No digits
        "first_name": "John",
        "last_name": "Doe"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert "detail" in data
    error_msg = str(data["detail"]).lower()
    assert "number" in error_msg or "digit" in error_msg


def test_register_invalid_email_format(client):
    """Test email format validation
    
    Validates Requirement 2.1: Email format validation
    """
    registration_data = {
        "email": "not-an-email",  # Invalid email format
        "password": "SecurePass123",
        "first_name": "John",
        "last_name": "Doe"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_register_missing_required_fields(client):
    """Test validation of required fields"""
    # Missing password
    registration_data = {
        "email": "test@example.com",
        "first_name": "John",
        "last_name": "Doe"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_register_empty_first_name(client):
    """Test validation of first name"""
    registration_data = {
        "email": "test@example.com",
        "password": "SecurePass123",
        "first_name": "",  # Empty string
        "last_name": "Doe"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_register_empty_last_name(client):
    """Test validation of last name"""
    registration_data = {
        "email": "test@example.com",
        "password": "SecurePass123",
        "first_name": "John",
        "last_name": ""  # Empty string
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_register_password_hashed(client, db_session):
    """Test that password is hashed in database
    
    Validates Requirement 9.1: Password hashing
    """
    registration_data = {
        "email": "secure@example.com",
        "password": "MyPassword123",
        "first_name": "John",
        "last_name": "Doe"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    assert response.status_code == status.HTTP_201_CREATED
    
    # Verify password is hashed (not stored in plain text)
    user = db_session.query(User).filter(User.email == registration_data["email"]).first()
    assert user is not None
    assert user.password_hash != registration_data["password"]
    assert user.password_hash.startswith("$2b$")  # bcrypt hash format


def test_register_sets_default_role(client, db_session):
    """Test that new users get MEMBER role by default"""
    registration_data = {
        "email": "member@example.com",
        "password": "SecurePass123",
        "first_name": "John",
        "last_name": "Doe"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    assert response.status_code == status.HTTP_201_CREATED
    
    user = db_session.query(User).filter(User.email == registration_data["email"]).first()
    assert user.role == UserRole.MEMBER


def test_register_password_max_length(client):
    """Test password maximum length (bcrypt limit is 72 bytes)"""
    registration_data = {
        "email": "test@example.com",
        "password": "A" * 73 + "bc123",  # Exceeds 72 character limit
        "first_name": "John",
        "last_name": "Doe"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    # Should be rejected by Pydantic validation (max_length=72)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

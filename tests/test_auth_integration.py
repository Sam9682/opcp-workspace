"""Integration tests for authentication flow

Tests the complete authentication flow from registration to login.
"""
import pytest
from fastapi import status
from app.models import User


def test_complete_auth_flow_verified_user(client, db_session):
    """Test complete authentication flow: register -> verify -> login"""
    # Step 1: Register a new user
    registration_data = {
        "email": "integration@example.com",
        "password": "SecurePass123",
        "first_name": "Integration",
        "last_name": "Test"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    assert response.status_code == status.HTTP_201_CREATED
    
    # Step 2: Manually verify the user (simulating email verification)
    user = db_session.query(User).filter(User.email == registration_data["email"]).first()
    assert user is not None
    assert user.is_email_verified is False
    
    user.is_email_verified = True
    db_session.commit()
    
    # Step 3: Login with verified account
    login_data = {
        "email": registration_data["email"],
        "password": registration_data["password"]
    }
    
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == registration_data["email"]
    assert data["user"]["is_email_verified"] is True


def test_cannot_login_before_email_verification(client, db_session):
    """Test that users cannot login before verifying their email"""
    # Step 1: Register a new user
    registration_data = {
        "email": "unverified@example.com",
        "password": "SecurePass123",
        "first_name": "Unverified",
        "last_name": "Test"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    assert response.status_code == status.HTTP_201_CREATED
    
    # Step 2: Try to login without verifying email
    login_data = {
        "email": registration_data["email"],
        "password": registration_data["password"]
    }
    
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "EMAIL_NOT_VERIFIED"


def test_rate_limiting_across_registration_and_login(client, db_session):
    """Test that rate limiting works independently for registration and login"""
    # Register a user
    registration_data = {
        "email": "ratelimit@example.com",
        "password": "SecurePass123",
        "first_name": "Rate",
        "last_name": "Limit"
    }
    
    response = client.post("/api/auth/register", json=registration_data)
    assert response.status_code == status.HTTP_201_CREATED
    
    # Verify the user
    user = db_session.query(User).filter(User.email == registration_data["email"]).first()
    user.is_email_verified = True
    db_session.commit()
    
    # Make 5 failed login attempts
    for i in range(5):
        response = client.post("/api/auth/login", json={
            "email": registration_data["email"],
            "password": "WrongPassword123"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # 6th attempt should be rate limited
    response = client.post("/api/auth/login", json={
        "email": registration_data["email"],
        "password": "WrongPassword123"
    })
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    
    # But registration with a different email should still work
    response = client.post("/api/auth/register", json={
        "email": "another@example.com",
        "password": "SecurePass123",
        "first_name": "Another",
        "last_name": "User"
    })
    assert response.status_code == status.HTTP_201_CREATED

"""Unit tests for email verification endpoint

Tests Requirement 2.6:
- Email verification required before account activation
- Token-based verification
- Verification token validation
"""
import pytest
from fastapi import status
from app.models import User, UserRole, AuditLog
from app.auth.password import hash_password
from app.auth.token import create_access_token
from datetime import timedelta


@pytest.fixture
def unverified_user(db_session):
    """Create an unverified test user for verification tests"""
    user = User(
        email="unverified@example.com",
        password_hash=hash_password("SecurePass123"),
        first_name="Unverified",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def verified_user(db_session):
    """Create a verified test user"""
    user = User(
        email="verified@example.com",
        password_hash=hash_password("SecurePass123"),
        first_name="Verified",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_verify_email_valid_token(client, unverified_user, db_session):
    """Test successful email verification with valid token
    
    Validates Requirement 2.6: Email verification activates account
    """
    # Generate verification token
    verification_token = create_access_token(
        data={"sub": str(unverified_user.id), "type": "email_verification"},
        expires_delta=timedelta(hours=24)
    )
    
    verification_data = {
        "token": verification_token
    }
    
    response = client.post("/api/auth/verify-email", json=verification_data)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == unverified_user.email
    assert "verified successfully" in data["message"].lower()
    
    # Verify user is now verified in database
    db_session.refresh(unverified_user)
    assert unverified_user.is_email_verified is True
    
    # Verify action was logged
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.action == "EMAIL_VERIFIED",
        AuditLog.admin_id == unverified_user.id
    ).first()
    assert audit_log is not None
    assert audit_log.details["email"] == unverified_user.email


def test_verify_email_invalid_token(client):
    """Test email verification rejection with invalid token
    
    Validates Requirement 2.6: Token validation
    """
    verification_data = {
        "token": "invalid.token.here"
    }
    
    response = client.post("/api/auth/verify-email", json=verification_data)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "INVALID_TOKEN"
    assert "invalid" in error["message"].lower()


def test_verify_email_expired_token(client, unverified_user):
    """Test email verification rejection with expired token
    
    Validates Requirement 2.6: Token expiration
    """
    # Generate expired token (negative expiration)
    expired_token = create_access_token(
        data={"sub": str(unverified_user.id), "type": "email_verification"},
        expires_delta=timedelta(seconds=-1)
    )
    
    verification_data = {
        "token": expired_token
    }
    
    response = client.post("/api/auth/verify-email", json=verification_data)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "INVALID_TOKEN"
    assert "expired" in error["message"].lower() or "invalid" in error["message"].lower()


def test_verify_email_wrong_token_type(client, unverified_user):
    """Test email verification rejection with wrong token type
    
    Validates Requirement 2.6: Token type validation
    """
    # Generate regular access token instead of verification token
    wrong_token = create_access_token(
        data={"sub": str(unverified_user.id)},  # Missing "type" field
        expires_delta=timedelta(hours=1)
    )
    
    verification_data = {
        "token": wrong_token
    }
    
    response = client.post("/api/auth/verify-email", json=verification_data)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "INVALID_TOKEN"


def test_verify_email_already_verified(client, verified_user):
    """Test email verification rejection when already verified
    
    Validates Requirement 2.6: Prevent duplicate verification
    """
    # Generate verification token for already verified user
    verification_token = create_access_token(
        data={"sub": str(verified_user.id), "type": "email_verification"},
        expires_delta=timedelta(hours=24)
    )
    
    verification_data = {
        "token": verification_token
    }
    
    response = client.post("/api/auth/verify-email", json=verification_data)
    
    assert response.status_code == status.HTTP_409_CONFLICT
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "EMAIL_ALREADY_VERIFIED"
    assert "already verified" in error["message"].lower()


def test_verify_email_nonexistent_user(client):
    """Test email verification rejection with non-existent user
    
    Validates Requirement 2.6: User validation
    """
    # Generate token with fake user ID
    fake_token = create_access_token(
        data={"sub": "00000000-0000-0000-0000-000000000000", "type": "email_verification"},
        expires_delta=timedelta(hours=24)
    )
    
    verification_data = {
        "token": fake_token
    }
    
    response = client.post("/api/auth/verify-email", json=verification_data)
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "USER_NOT_FOUND"


def test_verify_email_missing_token(client):
    """Test validation of required token field"""
    verification_data = {}
    
    response = client.post("/api/auth/verify-email", json=verification_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_verify_email_empty_token(client):
    """Test validation of empty token"""
    verification_data = {
        "token": ""
    }
    
    response = client.post("/api/auth/verify-email", json=verification_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_verify_email_token_missing_user_id(client):
    """Test email verification rejection with token missing user ID
    
    Validates Requirement 2.6: Token format validation
    """
    # Generate token without user ID
    invalid_token = create_access_token(
        data={"type": "email_verification"},  # Missing "sub" field
        expires_delta=timedelta(hours=24)
    )
    
    verification_data = {
        "token": invalid_token
    }
    
    response = client.post("/api/auth/verify-email", json=verification_data)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "INVALID_TOKEN"


def test_verify_email_allows_login_after_verification(client, unverified_user, db_session):
    """Test that user can login after email verification
    
    Validates Requirement 2.6: Email verification enables login
    """
    # Verify email
    verification_token = create_access_token(
        data={"sub": str(unverified_user.id), "type": "email_verification"},
        expires_delta=timedelta(hours=24)
    )
    
    verification_data = {
        "token": verification_token
    }
    
    response = client.post("/api/auth/verify-email", json=verification_data)
    assert response.status_code == status.HTTP_200_OK
    
    # Attempt login
    login_data = {
        "email": unverified_user.email,
        "password": "SecurePass123"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["user"]["is_email_verified"] is True


def test_verify_email_audit_log_includes_timestamp(client, unverified_user, db_session):
    """Test that audit log includes timestamp for email verification
    
    Validates Requirement 2.6: Audit logging
    """
    # Generate verification token
    verification_token = create_access_token(
        data={"sub": str(unverified_user.id), "type": "email_verification"},
        expires_delta=timedelta(hours=24)
    )
    
    verification_data = {
        "token": verification_token
    }
    
    response = client.post("/api/auth/verify-email", json=verification_data)
    assert response.status_code == status.HTTP_200_OK
    
    # Verify audit log has timestamp
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.action == "EMAIL_VERIFIED",
        AuditLog.admin_id == unverified_user.id
    ).first()
    assert audit_log is not None
    assert audit_log.timestamp is not None

"""Unit tests for user login endpoint

Tests Requirements 2.3, 2.4, 2.6, 9.6:
- Valid credentials authenticate
- Invalid credentials rejection
- Email verification required
- Authentication attempts logged
- Rate limiting (5 attempts per 15 minutes)
"""
import pytest
from fastapi import status
from app.models import User, UserRole, AuditLog
from app.auth.password import hash_password
from app.auth.rate_limiter import login_rate_limiter


@pytest.fixture
def verified_user(db_session):
    """Create a verified test user for login tests"""
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


@pytest.fixture
def unverified_user(db_session):
    """Create an unverified test user for login tests"""
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


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter before each test"""
    login_rate_limiter._attempts.clear()
    yield
    login_rate_limiter._attempts.clear()


def test_login_valid_credentials(client, verified_user, db_session):
    """Test successful login with valid credentials
    
    Validates Requirement 2.3: Valid credentials authenticate
    """
    login_data = {
        "email": verified_user.email,
        "password": "SecurePass123"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert data["user"]["email"] == verified_user.email
    assert data["user"]["first_name"] == verified_user.first_name
    assert data["user"]["last_name"] == verified_user.last_name
    assert data["user"]["role"] == verified_user.role.value
    
    # Verify successful login was logged (Requirement 9.6)
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.action == "LOGIN_SUCCESS",
        AuditLog.admin_id == verified_user.id
    ).first()
    assert audit_log is not None
    assert audit_log.details["email"] == verified_user.email


def test_login_invalid_password(client, verified_user, db_session):
    """Test login rejection with invalid password
    
    Validates Requirement 2.4: Invalid credentials rejection
    """
    login_data = {
        "email": verified_user.email,
        "password": "WrongPassword123"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert "detail" in data
    error = data["detail"]["error"]
    assert error["code"] == "INVALID_CREDENTIALS"
    assert "invalid" in error["message"].lower()
    
    # Verify failed login was logged (Requirement 9.6)
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.action == "LOGIN_FAILED",
        AuditLog.admin_id == verified_user.id
    ).first()
    assert audit_log is not None
    assert audit_log.details["reason"] == "invalid_credentials"


def test_login_nonexistent_email(client, db_session):
    """Test login rejection with non-existent email
    
    Validates Requirement 2.4: Invalid credentials rejection
    """
    login_data = {
        "email": "nonexistent@example.com",
        "password": "SecurePass123"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "INVALID_CREDENTIALS"
    # Should not reveal if email exists
    assert "invalid" in error["message"].lower()
    
    # Verify failed login was logged (Requirement 9.6)
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.action == "LOGIN_FAILED"
    ).first()
    assert audit_log is not None
    assert audit_log.admin_id is None  # No user exists
    assert audit_log.details["email"] == "nonexistent@example.com"


def test_login_unverified_email(client, unverified_user, db_session):
    """Test login rejection with unverified email
    
    Validates Requirement 2.6: Email verification required
    """
    login_data = {
        "email": unverified_user.email,
        "password": "SecurePass123"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "EMAIL_NOT_VERIFIED"
    assert "verify" in error["message"].lower()
    
    # Verify failed login was logged (Requirement 9.6)
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.action == "LOGIN_FAILED",
        AuditLog.admin_id == unverified_user.id
    ).first()
    assert audit_log is not None
    assert audit_log.details["reason"] == "email_not_verified"


def test_login_rate_limiting(client, verified_user):
    """Test rate limiting on login attempts
    
    Validates Requirement 9.6: Rate limiting (5 attempts per 15 minutes)
    """
    login_data = {
        "email": verified_user.email,
        "password": "WrongPassword123"
    }
    
    # Make 5 failed attempts
    for i in range(5):
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # 6th attempt should be rate limited
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "RATE_LIMIT_EXCEEDED"
    assert "too many" in error["message"].lower()


def test_login_rate_limit_reset_on_success(client, verified_user):
    """Test that rate limiter resets on successful login"""
    # Make 3 failed attempts
    for i in range(3):
        response = client.post("/api/auth/login", json={
            "email": verified_user.email,
            "password": "WrongPassword123"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Successful login should reset the counter
    response = client.post("/api/auth/login", json={
        "email": verified_user.email,
        "password": "SecurePass123"
    })
    assert response.status_code == status.HTTP_200_OK
    
    # Should be able to make more attempts now
    for i in range(5):
        response = client.post("/api/auth/login", json={
            "email": verified_user.email,
            "password": "WrongPassword123"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_missing_email(client):
    """Test validation of required email field"""
    login_data = {
        "password": "SecurePass123"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_login_missing_password(client):
    """Test validation of required password field"""
    login_data = {
        "email": "test@example.com"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_login_invalid_email_format(client):
    """Test email format validation"""
    login_data = {
        "email": "not-an-email",
        "password": "SecurePass123"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_login_empty_password(client):
    """Test validation of empty password"""
    login_data = {
        "email": "test@example.com",
        "password": ""
    }
    
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_login_jwt_token_contains_user_info(client, verified_user):
    """Test that JWT token contains user information"""
    from app.auth.token import verify_token
    
    login_data = {
        "email": verified_user.email,
        "password": "SecurePass123"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    token = data["access_token"]
    
    # Verify token contains user information
    payload = verify_token(token)
    assert payload is not None
    assert payload["sub"] == str(verified_user.id)
    assert payload["email"] == verified_user.email
    assert payload["role"] == verified_user.role.value


def test_login_different_users_separate_rate_limits(client, verified_user, db_session):
    """Test that rate limiting is per-user, not global"""
    # Create another verified user
    user2 = User(
        email="user2@example.com",
        password_hash=hash_password("SecurePass123"),
        first_name="User",
        last_name="Two",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user2)
    db_session.commit()
    
    # Make 5 failed attempts for user1
    for i in range(5):
        response = client.post("/api/auth/login", json={
            "email": verified_user.email,
            "password": "WrongPassword123"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # user1 should be rate limited
    response = client.post("/api/auth/login", json={
        "email": verified_user.email,
        "password": "WrongPassword123"
    })
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    
    # user2 should still be able to login
    response = client.post("/api/auth/login", json={
        "email": user2.email,
        "password": "SecurePass123"
    })
    assert response.status_code == status.HTTP_200_OK


def test_login_audit_log_includes_timestamp(client, verified_user, db_session):
    """Test that audit log includes timestamp for authentication attempts
    
    Validates Requirement 9.6: Log authentication attempts with timestamp
    """
    login_data = {
        "email": verified_user.email,
        "password": "SecurePass123"
    }
    
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_200_OK
    
    # Verify audit log has timestamp
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.action == "LOGIN_SUCCESS",
        AuditLog.admin_id == verified_user.id
    ).first()
    assert audit_log is not None
    assert audit_log.timestamp is not None

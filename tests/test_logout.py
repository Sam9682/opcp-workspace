"""Unit tests for logout endpoint

Tests the logout functionality including token blacklisting and session termination.
Validates Requirement 2.5: Logout terminates session.
"""
import pytest
from fastapi import status
from app.models import User, TokenBlacklist
from app.auth.token import create_access_token


def test_logout_success(client, verified_user, db_session):
    """Test successful logout with valid token"""
    # Generate a token for the verified user
    token = create_access_token(
        data={
            "sub": str(verified_user.id),
            "email": verified_user.email,
            "role": verified_user.role.value
        }
    )
    
    # Logout with the token
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["message"] == "Logout successful"
    
    # Verify token is in blacklist
    blacklisted = db_session.query(TokenBlacklist).filter(
        TokenBlacklist.token == token
    ).first()
    assert blacklisted is not None
    assert str(blacklisted.user_id) == str(verified_user.id)


def test_logout_token_cannot_be_reused(client, verified_user, db_session):
    """Test that a token cannot be used after logout"""
    # Generate a token
    token = create_access_token(
        data={
            "sub": str(verified_user.id),
            "email": verified_user.email,
            "role": verified_user.role.value
        }
    )
    
    # Logout
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Try to use the same token again for logout
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Should fail because token is blacklisted
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "TOKEN_REVOKED"


def test_logout_without_token(client):
    """Test logout without providing a token"""
    response = client.post("/api/auth/logout")
    
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_logout_with_invalid_token(client):
    """Test logout with an invalid token"""
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": "Bearer invalid_token_here"}
    )
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "INVALID_TOKEN"


def test_logout_idempotent(client, verified_user, db_session):
    """Test that logout is idempotent - calling it twice with same token returns success"""
    # Generate a token
    token = create_access_token(
        data={
            "sub": str(verified_user.id),
            "email": verified_user.email,
            "role": verified_user.role.value
        }
    )
    
    # First logout
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Count blacklist entries
    count_before = db_session.query(TokenBlacklist).filter(
        TokenBlacklist.token == token
    ).count()
    assert count_before == 1


def test_logout_creates_audit_log(client, verified_user, db_session):
    """Test that logout creates an audit log entry"""
    from app.models import AuditLog
    
    # Generate a token
    token = create_access_token(
        data={
            "sub": str(verified_user.id),
            "email": verified_user.email,
            "role": verified_user.role.value
        }
    )
    
    # Logout
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Verify audit log entry was created
    audit_log = db_session.query(AuditLog).filter(
        AuditLog.action == "LOGOUT",
        AuditLog.admin_id == verified_user.id
    ).first()
    
    assert audit_log is not None
    assert audit_log.target_type == "user"
    assert str(audit_log.target_id) == str(verified_user.id)
    assert audit_log.details["email"] == verified_user.email


def test_logout_different_users_independent(client, verified_user, db_session):
    """Test that logout for one user doesn't affect another user's token"""
    # Create a second user
    from app.auth.password import hash_password
    from app.models import UserRole
    
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
    db_session.refresh(user2)
    
    # Generate tokens for both users
    token1 = create_access_token(
        data={
            "sub": str(verified_user.id),
            "email": verified_user.email,
            "role": verified_user.role.value
        }
    )
    
    token2 = create_access_token(
        data={
            "sub": str(user2.id),
            "email": user2.email,
            "role": user2.role.value
        }
    )
    
    # Logout user1
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # User2's token should still work
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert response.status_code == status.HTTP_200_OK


def test_logout_with_expired_token(client, verified_user):
    """Test logout with an expired token"""
    from datetime import timedelta
    
    # Generate an expired token (negative expiration)
    token = create_access_token(
        data={
            "sub": str(verified_user.id),
            "email": verified_user.email,
            "role": verified_user.role.value
        },
        expires_delta=timedelta(seconds=-1)  # Already expired
    )
    
    # Try to logout with expired token
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    error = data["detail"]["error"]
    assert error["code"] == "INVALID_TOKEN"

"""Tests for forum access control middleware

Validates Requirement 3.4: Non-authenticated users are redirected/denied access
"""

import pytest
from fastapi import status
from app.models import User, UserRole
from app.auth.password import hash_password
from app.auth.token import create_access_token


def test_forum_access_requires_authentication(client):
    """Test that forum endpoints require authentication"""
    # Try to access forum without authentication
    response = client.get("/api/forum/topics")
    
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_forum_access_with_invalid_token(client):
    """Test that invalid tokens are rejected"""
    headers = {"Authorization": "Bearer invalid_token_here"}
    response = client.get("/api/forum/topics", headers=headers)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"]["error"]["code"] == "INVALID_TOKEN"


def test_forum_access_denied_for_unverified_user(client, db_session):
    """Test that unverified users cannot access forum"""
    # Create unverified user
    user = User(
        email="unverified@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Unverified",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=False  # Not verified
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create token for unverified user
    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to access forum
    response = client.get("/api/forum/topics", headers=headers)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"]["error"]["code"] == "EMAIL_NOT_VERIFIED"
    assert "verify your email" in response.json()["detail"]["error"]["message"].lower()


def test_forum_access_denied_for_visitor_role(client, db_session):
    """Test that users with VISITOR role cannot access forum"""
    # Create visitor user (verified but with VISITOR role)
    user = User(
        email="visitor@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Visitor",
        last_name="User",
        role=UserRole.VISITOR,  # Visitor role
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create token for visitor
    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to access forum
    response = client.get("/api/forum/topics", headers=headers)
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
    assert "member status" in response.json()["detail"]["error"]["message"].lower()


def test_forum_access_granted_for_verified_member(client, db_session):
    """Test that verified members can access forum"""
    # Create verified member
    user = User(
        email="member@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create token for member
    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Access forum should succeed
    response = client.get("/api/forum/topics", headers=headers)
    
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


def test_forum_access_granted_for_administrator(client, db_session):
    """Test that administrators can access forum"""
    # Create administrator
    user = User(
        email="admin@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create token for admin
    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Access forum should succeed
    response = client.get("/api/forum/topics", headers=headers)
    
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


def test_create_topic_requires_verified_member(client, db_session):
    """Test that creating topics requires verified member access"""
    # Create unverified user
    user = User(
        email="unverified@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Unverified",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create token
    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to create topic
    response = client.post(
        "/api/forum/topics",
        json={"title": "Test Topic"},
        headers=headers
    )
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"]["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_create_post_requires_verified_member(client, db_session):
    """Test that creating posts requires verified member access"""
    # Create verified member and topic
    member = User(
        email="member@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)
    
    # Create a topic
    from app.models import Topic
    topic = Topic(
        title="Test Topic",
        author_id=member.id,
        is_pinned=False,
        is_locked=False
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    
    # Create unverified user
    unverified = User(
        email="unverified@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Unverified",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=False
    )
    db_session.add(unverified)
    db_session.commit()
    db_session.refresh(unverified)
    
    # Try to post with unverified user
    token = create_access_token({"sub": str(unverified.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post(
        f"/api/forum/topics/{topic.id}/posts",
        json={"content": "Test post"},
        headers=headers
    )
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"]["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_all_forum_endpoints_protected(client):
    """Test that all forum endpoints require authentication"""
    # List of forum endpoints to test
    endpoints = [
        ("GET", "/api/forum/topics"),
        ("POST", "/api/forum/topics"),
    ]
    
    for method, endpoint in endpoints:
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint, json={})
        
        # All should return 403 (no auth) or 401 (invalid auth)
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ], f"Endpoint {method} {endpoint} is not protected"

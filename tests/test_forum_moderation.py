"""Tests for forum content moderation endpoints

Tests the content moderation endpoints:
- PUT /api/forum/posts/:id/hide (hide post - admin only)

Validates Requirements 3.5, 7.2, 7.5
"""

import pytest
from fastapi import status
from app.models import User, Topic, Post, AuditLog, UserRole
from app.auth.token import create_access_token


@pytest.fixture
def verified_member(db_session):
    """Create a verified member for testing"""
    user = User(
        email="member@test.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def administrator(db_session):
    """Create an administrator for testing"""
    user = User(
        email="admin@test.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def member_headers(verified_member):
    """Create authentication headers for verified member"""
    token = create_access_token({"sub": str(verified_member.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(administrator):
    """Create authentication headers for administrator"""
    token = create_access_token({"sub": str(administrator.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_topic(db_session, verified_member):
    """Create a test topic"""
    topic = Topic(
        title="Test Topic",
        author_id=verified_member.id,
        is_pinned=False,
        is_locked=False
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    return topic


@pytest.fixture
def test_post(db_session, test_topic, verified_member):
    """Create a test post"""
    post = Post(
        topic_id=test_topic.id,
        author_id=verified_member.id,
        content="This is a test post that may contain inappropriate content",
        is_hidden=False
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    return post


def test_hide_post_success(client, administrator, test_post, admin_headers, db_session):
    """Test hiding a post successfully as administrator
    
    Validates Requirement 3.5: Administrator can flag inappropriate content
    Validates Requirement 7.2: Administrative functions restricted to administrators
    Validates Requirement 7.5: Administrative actions logged in audit log
    """
    response = client.put(
        f"/api/forum/posts/{test_post.id}/hide",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Verify response structure
    assert data["success"] is True
    assert "message" in data
    assert data["post_id"] == str(test_post.id)
    
    # Verify post is marked as hidden in database (Requirement 3.5)
    db_session.refresh(test_post)
    assert test_post.is_hidden is True
    
    # Verify audit log entry was created (Requirement 7.5)
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.admin_id == administrator.id,
        AuditLog.action == "hide_post",
        AuditLog.target_id == test_post.id
    ).first()
    
    assert audit_entry is not None
    assert audit_entry.target_type == "post"
    assert audit_entry.details["post_id"] == str(test_post.id)
    assert audit_entry.details["topic_id"] == str(test_post.topic_id)
    assert audit_entry.details["author_id"] == str(test_post.author_id)
    assert "content_preview" in audit_entry.details


def test_hide_post_non_admin_forbidden(client, verified_member, test_post, member_headers):
    """Test that non-admin users cannot hide posts
    
    Validates Requirement 7.2: Administrative functions restricted to administrators
    """
    response = client.put(
        f"/api/forum/posts/{test_post.id}/hide",
        headers=member_headers
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert data["detail"]["error"]["code"] == "ADMIN_ACCESS_REQUIRED"


def test_hide_post_not_found(client, admin_headers):
    """Test hiding non-existent post returns 404"""
    from uuid import uuid4
    
    fake_post_id = uuid4()
    
    response = client.put(
        f"/api/forum/posts/{fake_post_id}/hide",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert data["detail"]["error"]["code"] == "POST_NOT_FOUND"


def test_hide_post_invalid_id(client, admin_headers):
    """Test hiding post with invalid UUID format returns 400"""
    response = client.put(
        "/api/forum/posts/invalid-uuid/hide",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["detail"]["error"]["code"] == "INVALID_POST_ID"


def test_hide_post_requires_authentication(client, test_post):
    """Test that hiding post requires authentication"""
    response = client.put(f"/api/forum/posts/{test_post.id}/hide")
    
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_hidden_post_excluded_from_topic_view(client, administrator, test_post, test_topic, admin_headers, member_headers, db_session):
    """Test that hidden posts are excluded from normal topic display
    
    Validates Requirement 3.5: Hidden content excluded from normal display
    """
    # Create another visible post
    visible_post = Post(
        topic_id=test_topic.id,
        author_id=administrator.id,
        content="This post is visible",
        is_hidden=False
    )
    db_session.add(visible_post)
    db_session.commit()
    
    # Hide the first post
    response = client.put(
        f"/api/forum/posts/{test_post.id}/hide",
        headers=admin_headers
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Fetch topic as regular member
    topic_response = client.get(
        f"/api/forum/topics/{test_topic.id}",
        headers=member_headers
    )
    
    assert topic_response.status_code == status.HTTP_200_OK
    topic_data = topic_response.json()
    
    # Verify only visible post is shown
    assert len(topic_data["posts"]) == 1
    assert topic_data["posts"][0]["id"] == str(visible_post.id)
    assert topic_data["posts"][0]["content"] == "This post is visible"


def test_hide_already_hidden_post(client, administrator, test_post, admin_headers, db_session):
    """Test hiding an already hidden post (idempotent operation)"""
    # Hide post first time
    response1 = client.put(
        f"/api/forum/posts/{test_post.id}/hide",
        headers=admin_headers
    )
    assert response1.status_code == status.HTTP_200_OK
    
    # Hide post second time
    response2 = client.put(
        f"/api/forum/posts/{test_post.id}/hide",
        headers=admin_headers
    )
    assert response2.status_code == status.HTTP_200_OK
    
    # Verify post is still hidden
    db_session.refresh(test_post)
    assert test_post.is_hidden is True
    
    # Verify two audit log entries were created
    audit_entries = db_session.query(AuditLog).filter(
        AuditLog.admin_id == administrator.id,
        AuditLog.action == "hide_post",
        AuditLog.target_id == test_post.id
    ).all()
    
    assert len(audit_entries) == 2


def test_hide_post_with_long_content(client, administrator, test_topic, verified_member, admin_headers, db_session):
    """Test hiding post with long content truncates preview in audit log"""
    long_content = "This is a very long post content. " * 50  # > 100 characters
    
    long_post = Post(
        topic_id=test_topic.id,
        author_id=verified_member.id,
        content=long_content,
        is_hidden=False
    )
    db_session.add(long_post)
    db_session.commit()
    db_session.refresh(long_post)
    
    response = client.put(
        f"/api/forum/posts/{long_post.id}/hide",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Verify audit log has truncated content preview
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.target_id == long_post.id
    ).first()
    
    assert audit_entry is not None
    assert len(audit_entry.details["content_preview"]) == 100


def test_hide_post_audit_log_contains_all_details(client, administrator, test_post, admin_headers, db_session):
    """Test that audit log contains all required details
    
    Validates Requirement 7.5: Audit log with timestamp and administrator identity
    """
    response = client.put(
        f"/api/forum/posts/{test_post.id}/hide",
        headers=admin_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    # Fetch audit log entry
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.target_id == test_post.id
    ).first()
    
    # Verify all required fields
    assert audit_entry.admin_id == administrator.id
    assert audit_entry.action == "hide_post"
    assert audit_entry.target_type == "post"
    assert audit_entry.target_id == test_post.id
    assert audit_entry.timestamp is not None
    
    # Verify details
    assert "post_id" in audit_entry.details
    assert "topic_id" in audit_entry.details
    assert "author_id" in audit_entry.details
    assert "content_preview" in audit_entry.details


def test_multiple_posts_hide_independently(client, administrator, test_topic, verified_member, admin_headers, member_headers, db_session):
    """Test that hiding one post doesn't affect other posts"""
    # Create multiple posts
    post1 = Post(
        topic_id=test_topic.id,
        author_id=verified_member.id,
        content="First post",
        is_hidden=False
    )
    post2 = Post(
        topic_id=test_topic.id,
        author_id=verified_member.id,
        content="Second post",
        is_hidden=False
    )
    post3 = Post(
        topic_id=test_topic.id,
        author_id=verified_member.id,
        content="Third post",
        is_hidden=False
    )
    db_session.add_all([post1, post2, post3])
    db_session.commit()
    
    # Hide only the second post
    response = client.put(
        f"/api/forum/posts/{post2.id}/hide",
        headers=admin_headers
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Fetch topic
    topic_response = client.get(
        f"/api/forum/topics/{test_topic.id}",
        headers=member_headers
    )
    
    topic_data = topic_response.json()
    visible_posts = topic_data["posts"]
    
    # Verify only post2 is hidden
    assert len(visible_posts) == 2
    visible_contents = [p["content"] for p in visible_posts]
    assert "First post" in visible_contents
    assert "Second post" not in visible_contents
    assert "Third post" in visible_contents


def test_hide_post_different_admins(client, test_post, db_session):
    """Test that different administrators can hide posts"""
    # Create two administrators
    admin1 = User(
        email="admin1@test.com",
        password_hash="hashed",
        first_name="Admin",
        last_name="One",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    admin2 = User(
        email="admin2@test.com",
        password_hash="hashed",
        first_name="Admin",
        last_name="Two",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add_all([admin1, admin2])
    db_session.commit()
    
    # First admin hides post
    token1 = create_access_token({"sub": str(admin1.id)})
    headers1 = {"Authorization": f"Bearer {token1}"}
    
    response1 = client.put(
        f"/api/forum/posts/{test_post.id}/hide",
        headers=headers1
    )
    assert response1.status_code == status.HTTP_200_OK
    
    # Verify audit log shows admin1
    audit1 = db_session.query(AuditLog).filter(
        AuditLog.admin_id == admin1.id,
        AuditLog.target_id == test_post.id
    ).first()
    assert audit1 is not None
    
    # Second admin can also hide (already hidden) post
    token2 = create_access_token({"sub": str(admin2.id)})
    headers2 = {"Authorization": f"Bearer {token2}"}
    
    response2 = client.put(
        f"/api/forum/posts/{test_post.id}/hide",
        headers=headers2
    )
    assert response2.status_code == status.HTTP_200_OK
    
    # Verify audit log shows admin2
    audit2 = db_session.query(AuditLog).filter(
        AuditLog.admin_id == admin2.id,
        AuditLog.target_id == test_post.id
    ).first()
    assert audit2 is not None

"""Tests for forum post API endpoints

Tests the post management endpoints:
- POST /api/forum/topics/:id/posts (create reply to topic)

Validates Requirements 3.3, 3.6
"""

import pytest
import time
from fastapi import status
from app.models import User, Topic, Post
from app.auth.token import create_access_token


@pytest.fixture
def verified_member(db_session):
    """Create a verified member for testing"""
    user = User(
        email="member@test.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="Member",
        role="member",
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def another_member(db_session):
    """Create another verified member for testing"""
    user = User(
        email="another@test.com",
        password_hash="hashed_password",
        first_name="Another",
        last_name="User",
        role="member",
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(verified_member):
    """Create authentication headers for verified member"""
    token = create_access_token({"sub": str(verified_member.id)})
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


def test_create_post_success(client, verified_member, test_topic, auth_headers, db_session):
    """Test creating a post successfully
    
    Validates Requirement 3.3: Add reply to topic
    Validates Requirement 3.6: Include author name and timestamp
    """
    post_data = {"content": "This is my reply to the topic"}
    
    response = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    # Verify response structure
    assert "id" in data
    assert data["topic_id"] == str(test_topic.id)
    assert data["author_id"] == str(verified_member.id)
    assert data["author_name"] == "Test Member"  # Requirement 3.6
    assert data["content"] == "This is my reply to the topic"
    assert data["is_hidden"] is False
    assert "created_at" in data  # Requirement 3.6
    assert "updated_at" in data
    
    # Verify post was created in database
    post = db_session.query(Post).filter(
        Post.topic_id == test_topic.id,
        Post.content == "This is my reply to the topic"
    ).first()
    assert post is not None
    assert post.author_id == verified_member.id


def test_create_post_empty_content(client, test_topic, auth_headers):
    """Test creating post with empty content fails validation"""
    post_data = {"content": ""}
    
    response = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_post_missing_content(client, test_topic, auth_headers):
    """Test creating post without content fails validation"""
    post_data = {}
    
    response = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_post_topic_not_found(client, auth_headers):
    """Test creating post for non-existent topic returns 404"""
    from uuid import uuid4
    
    fake_topic_id = uuid4()
    post_data = {"content": "Test post"}
    
    response = client.post(
        f"/api/forum/topics/{fake_topic_id}/posts",
        json=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert data["detail"]["error"]["code"] == "TOPIC_NOT_FOUND"


def test_create_post_invalid_topic_id(client, auth_headers):
    """Test creating post with invalid topic UUID format returns 400"""
    post_data = {"content": "Test post"}
    
    response = client.post(
        "/api/forum/topics/invalid-uuid/posts",
        json=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["detail"]["error"]["code"] == "INVALID_TOPIC_ID"


def test_create_post_locked_topic(client, verified_member, auth_headers, db_session):
    """Test creating post in locked topic returns 403"""
    # Create locked topic
    locked_topic = Topic(
        title="Locked Topic",
        author_id=verified_member.id,
        is_pinned=False,
        is_locked=True
    )
    db_session.add(locked_topic)
    db_session.commit()
    db_session.refresh(locked_topic)
    
    post_data = {"content": "Trying to post in locked topic"}
    
    response = client.post(
        f"/api/forum/topics/{locked_topic.id}/posts",
        json=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert data["detail"]["error"]["code"] == "TOPIC_LOCKED"


def test_create_multiple_posts_chronological_order(client, verified_member, another_member, test_topic, auth_headers, db_session):
    """Test that multiple posts are ordered chronologically
    
    Validates Requirement 3.3: Posts ordered chronologically by created_at
    """
    # Create first post
    post1_data = {"content": "First post"}
    response1 = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post1_data,
        headers=auth_headers
    )
    assert response1.status_code == status.HTTP_201_CREATED
    
    time.sleep(0.01)  # Small delay to ensure different timestamps
    
    # Create second post by another user
    another_token = create_access_token({"sub": str(another_member.id)})
    another_headers = {"Authorization": f"Bearer {another_token}"}
    
    post2_data = {"content": "Second post"}
    response2 = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post2_data,
        headers=another_headers
    )
    assert response2.status_code == status.HTTP_201_CREATED
    
    time.sleep(0.01)  # Small delay
    
    # Create third post
    post3_data = {"content": "Third post"}
    response3 = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post3_data,
        headers=auth_headers
    )
    assert response3.status_code == status.HTTP_201_CREATED
    
    # Fetch topic to verify chronological order
    topic_response = client.get(f"/api/forum/topics/{test_topic.id}", headers=auth_headers)
    assert topic_response.status_code == status.HTTP_200_OK
    
    topic_data = topic_response.json()
    posts = topic_data["posts"]
    
    assert len(posts) == 3
    assert posts[0]["content"] == "First post"
    assert posts[1]["content"] == "Second post"
    assert posts[2]["content"] == "Third post"
    
    # Verify timestamps are in chronological order
    assert posts[0]["created_at"] <= posts[1]["created_at"]
    assert posts[1]["created_at"] <= posts[2]["created_at"]


def test_create_post_includes_author_metadata(client, verified_member, test_topic, auth_headers):
    """Test that post response includes author name and timestamp
    
    Validates Requirement 3.6: Display author and timestamp for each post
    """
    post_data = {"content": "Test post with metadata"}
    
    response = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    # Verify author metadata (Requirement 3.6)
    assert "author_name" in data
    assert data["author_name"] == "Test Member"
    assert data["author_id"] == str(verified_member.id)
    
    # Verify timestamp metadata (Requirement 3.6)
    assert "created_at" in data
    assert "updated_at" in data
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_create_post_by_different_users(client, verified_member, another_member, test_topic, auth_headers, db_session):
    """Test that different users can post to the same topic"""
    # First user posts
    post1_data = {"content": "Post by first user"}
    response1 = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post1_data,
        headers=auth_headers
    )
    assert response1.status_code == status.HTTP_201_CREATED
    assert response1.json()["author_name"] == "Test Member"
    
    # Second user posts
    another_token = create_access_token({"sub": str(another_member.id)})
    another_headers = {"Authorization": f"Bearer {another_token}"}
    
    post2_data = {"content": "Post by second user"}
    response2 = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post2_data,
        headers=another_headers
    )
    assert response2.status_code == status.HTTP_201_CREATED
    assert response2.json()["author_name"] == "Another User"
    
    # Verify both posts exist in database
    posts = db_session.query(Post).filter(Post.topic_id == test_topic.id).all()
    assert len(posts) == 2


def test_create_post_long_content(client, test_topic, auth_headers, db_session):
    """Test creating post with long content"""
    from uuid import UUID
    
    long_content = "This is a very long post. " * 100  # ~2700 characters
    post_data = {"content": long_content}
    
    response = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["content"] == long_content
    
    # Verify in database
    post_id = UUID(data["id"])
    post = db_session.query(Post).filter(Post.id == post_id).first()
    assert post.content == long_content


def test_create_post_with_special_characters(client, test_topic, auth_headers, db_session):
    """Test creating post with special characters and unicode"""
    special_content = "Test with special chars: @#$%^&*() and unicode: 你好 🎉 café"
    post_data = {"content": special_content}
    
    response = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["content"] == special_content


def test_create_post_requires_authentication(client, test_topic):
    """Test that creating post requires authentication"""
    post_data = {"content": "Test post"}
    
    response = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post_data
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_create_post_updates_topic_post_count(client, verified_member, test_topic, auth_headers):
    """Test that creating posts updates the topic's post count"""
    # Get initial topic state
    topic_response = client.get(f"/api/forum/topics/{test_topic.id}", headers=auth_headers)
    initial_count = topic_response.json()["post_count"]
    
    # Create a post
    post_data = {"content": "New post"}
    client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json=post_data,
        headers=auth_headers
    )
    
    # Get updated topic state
    topic_response = client.get(f"/api/forum/topics/{test_topic.id}", headers=auth_headers)
    updated_count = topic_response.json()["post_count"]
    
    assert updated_count == initial_count + 1


def test_create_post_in_pinned_topic(client, verified_member, auth_headers, db_session):
    """Test that posts can be created in pinned topics"""
    # Create pinned topic
    pinned_topic = Topic(
        title="Pinned Topic",
        author_id=verified_member.id,
        is_pinned=True,
        is_locked=False
    )
    db_session.add(pinned_topic)
    db_session.commit()
    db_session.refresh(pinned_topic)
    
    post_data = {"content": "Post in pinned topic"}
    
    response = client.post(
        f"/api/forum/topics/{pinned_topic.id}/posts",
        json=post_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["content"] == "Post in pinned topic"

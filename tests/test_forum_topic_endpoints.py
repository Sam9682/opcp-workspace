"""Tests for forum topic API endpoints

Tests the topic management endpoints:
- GET /api/forum/topics (list all topics)
- POST /api/forum/topics (create new topic)
- GET /api/forum/topics/:id (get topic with posts)

Validates Requirements 3.1, 3.2, 3.3, 3.4, 3.6
"""

import pytest
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


def test_list_topics_empty(client, verified_member, auth_headers):
    """Test listing topics when forum is empty"""
    response = client.get("/api/forum/topics", headers=auth_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_create_topic_success(client, verified_member, auth_headers, db_session):
    """Test creating a new topic successfully
    
    Validates Requirement 3.2: Topic creation and PSMC with user
    """
    topic_data = {"title": "My First Topic"}
    
    response = client.post(
        "/api/forum/topics",
        json=topic_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    # Verify response structure
    assert "id" in data
    assert data["title"] == "My First Topic"
    assert data["author_id"] == str(verified_member.id)
    assert data["author_name"] == "Test Member"
    assert data["is_pinned"] is False
    assert data["is_locked"] is False
    assert data["post_count"] == 0
    assert "created_at" in data
    assert "updated_at" in data
    
    # Verify topic was created in database
    topic = db_session.query(Topic).filter(Topic.title == "My First Topic").first()
    assert topic is not None
    assert topic.author_id == verified_member.id


def test_create_topic_empty_title(client, auth_headers):
    """Test creating topic with empty title fails validation"""
    topic_data = {"title": ""}
    
    response = client.post(
        "/api/forum/topics",
        json=topic_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_topic_missing_title(client, auth_headers):
    """Test creating topic without title fails validation"""
    topic_data = {}
    
    response = client.post(
        "/api/forum/topics",
        json=topic_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_create_topic_title_too_long(client, auth_headers):
    """Test creating topic with title exceeding max length"""
    topic_data = {"title": "x" * 256}  # Max is 255
    
    response = client.post(
        "/api/forum/topics",
        json=topic_data,
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_list_topics_with_data(client, verified_member, another_member, auth_headers, db_session):
    """Test listing topics returns all topics with correct data
    
    Validates Requirement 3.1: Display all discussion topics
    """
    # Create multiple topics
    topic1 = Topic(
        title="First Topic",
        author_id=verified_member.id,
        is_pinned=False,
        is_locked=False
    )
    topic2 = Topic(
        title="Second Topic",
        author_id=another_member.id,
        is_pinned=True,  # Pinned topic
        is_locked=False
    )
    topic3 = Topic(
        title="Third Topic",
        author_id=verified_member.id,
        is_pinned=False,
        is_locked=True  # Locked topic
    )
    
    db_session.add_all([topic1, topic2, topic3])
    db_session.commit()
    
    # Add some posts to topic1
    post1 = Post(
        topic_id=topic1.id,
        author_id=verified_member.id,
        content="First post",
        is_hidden=False
    )
    post2 = Post(
        topic_id=topic1.id,
        author_id=another_member.id,
        content="Second post",
        is_hidden=False
    )
    db_session.add_all([post1, post2])
    db_session.commit()
    
    response = client.get("/api/forum/topics", headers=auth_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert len(data) == 3
    
    # Verify pinned topics come first
    assert data[0]["title"] == "Second Topic"
    assert data[0]["is_pinned"] is True
    assert data[0]["author_name"] == "Another User"
    
    # Verify post count is correct
    topic_with_posts = next(t for t in data if t["title"] == "First Topic")
    assert topic_with_posts["post_count"] == 2
    
    # Verify locked status
    locked_topic = next(t for t in data if t["title"] == "Third Topic")
    assert locked_topic["is_locked"] is True


def test_get_topic_by_id_success(client, verified_member, auth_headers, db_session):
    """Test getting a specific topic with its posts
    
    Validates Requirement 3.1: Get topic details
    Validates Requirement 3.6: Display author and timestamp
    """
    # Create topic
    topic = Topic(
        title="Test Topic",
        author_id=verified_member.id,
        is_pinned=False,
        is_locked=False
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    
    response = client.get(f"/api/forum/topics/{topic.id}", headers=auth_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["id"] == str(topic.id)
    assert data["title"] == "Test Topic"
    assert data["author_id"] == str(verified_member.id)
    assert data["author_name"] == "Test Member"
    assert data["is_pinned"] is False
    assert data["is_locked"] is False
    assert "created_at" in data
    assert "updated_at" in data
    assert data["post_count"] == 0
    assert data["posts"] == []


def test_get_topic_with_posts(client, verified_member, another_member, auth_headers, db_session):
    """Test getting topic with multiple posts in chronological order
    
    Validates Requirement 3.3: Posts displayed chronologically
    Validates Requirement 3.6: Display author and timestamp for each post
    """
    import time
    
    # Create topic
    topic = Topic(
        title="Discussion Topic",
        author_id=verified_member.id,
        is_pinned=False,
        is_locked=False
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    
    # Create posts with slight time delays to ensure different timestamps
    post1 = Post(
        topic_id=topic.id,
        author_id=verified_member.id,
        content="First post content",
        is_hidden=False
    )
    db_session.add(post1)
    db_session.commit()
    
    time.sleep(0.01)  # Small delay
    
    post2 = Post(
        topic_id=topic.id,
        author_id=another_member.id,
        content="Second post content",
        is_hidden=False
    )
    db_session.add(post2)
    db_session.commit()
    
    time.sleep(0.01)  # Small delay
    
    post3 = Post(
        topic_id=topic.id,
        author_id=verified_member.id,
        content="Third post content",
        is_hidden=False
    )
    db_session.add(post3)
    db_session.commit()
    
    response = client.get(f"/api/forum/topics/{topic.id}", headers=auth_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["post_count"] == 3
    assert len(data["posts"]) == 3
    
    # Verify chronological order (oldest first)
    posts = data["posts"]
    assert posts[0]["content"] == "First post content"
    assert posts[0]["author_name"] == "Test Member"
    assert "created_at" in posts[0]
    assert "updated_at" in posts[0]
    
    assert posts[1]["content"] == "Second post content"
    assert posts[1]["author_name"] == "Another User"
    
    assert posts[2]["content"] == "Third post content"
    assert posts[2]["author_name"] == "Test Member"
    
    # Verify timestamps are in chronological order
    assert posts[0]["created_at"] <= posts[1]["created_at"]
    assert posts[1]["created_at"] <= posts[2]["created_at"]


def test_get_topic_hides_hidden_posts(client, verified_member, auth_headers, db_session):
    """Test that hidden posts are not shown to regular users
    
    Validates Requirement 3.5: Hidden content not displayed
    """
    # Create topic
    topic = Topic(
        title="Topic with Hidden Post",
        author_id=verified_member.id,
        is_pinned=False,
        is_locked=False
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    
    # Create visible post
    post1 = Post(
        topic_id=topic.id,
        author_id=verified_member.id,
        content="Visible post",
        is_hidden=False
    )
    # Create hidden post
    post2 = Post(
        topic_id=topic.id,
        author_id=verified_member.id,
        content="Hidden post",
        is_hidden=True
    )
    db_session.add_all([post1, post2])
    db_session.commit()
    
    response = client.get(f"/api/forum/topics/{topic.id}", headers=auth_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Should only show the visible post
    assert data["post_count"] == 1
    assert len(data["posts"]) == 1
    assert data["posts"][0]["content"] == "Visible post"


def test_get_topic_not_found(client, auth_headers):
    """Test getting non-existent topic returns 404"""
    from uuid import uuid4
    
    fake_id = uuid4()
    response = client.get(f"/api/forum/topics/{fake_id}", headers=auth_headers)
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "detail" in data


def test_get_topic_invalid_id(client, auth_headers):
    """Test getting topic with invalid UUID format returns 400"""
    response = client.get("/api/forum/topics/invalid-uuid", headers=auth_headers)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "detail" in data


def test_create_multiple_topics_by_same_user(client, verified_member, auth_headers, db_session):
    """Test that a user can create multiple topics"""
    # Create first topic
    response1 = client.post(
        "/api/forum/topics",
        json={"title": "First Topic"},
        headers=auth_headers
    )
    assert response1.status_code == status.HTTP_201_CREATED
    
    # Create second topic
    response2 = client.post(
        "/api/forum/topics",
        json={"title": "Second Topic"},
        headers=auth_headers
    )
    assert response2.status_code == status.HTTP_201_CREATED
    
    # Verify both topics exist
    topics = db_session.query(Topic).filter(Topic.author_id == verified_member.id).all()
    assert len(topics) == 2


def test_topic_ordering_pinned_first(client, verified_member, auth_headers, db_session):
    """Test that pinned topics appear first in the list"""
    # Create regular topic first
    topic1 = Topic(
        title="Regular Topic",
        author_id=verified_member.id,
        is_pinned=False,
        is_locked=False
    )
    db_session.add(topic1)
    db_session.commit()
    
    # Create pinned topic later
    topic2 = Topic(
        title="Pinned Topic",
        author_id=verified_member.id,
        is_pinned=True,
        is_locked=False
    )
    db_session.add(topic2)
    db_session.commit()
    
    response = client.get("/api/forum/topics", headers=auth_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Pinned topic should be first despite being created later
    assert data[0]["title"] == "Pinned Topic"
    assert data[0]["is_pinned"] is True
    assert data[1]["title"] == "Regular Topic"
    assert data[1]["is_pinned"] is False

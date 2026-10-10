"""Integration tests for forum notification delivery

Validates Requirements 10.2:
- Sends email notification when member receives forum reply
"""
import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models import User, Topic, NotificationPreferences, UserRole
from app.auth.password import hash_password
from app.auth.token import create_access_token


@pytest.fixture
def topic_author(db_session: Session):
    """Create a topic author user"""
    user = User(
        email="author@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Topic",
        last_name="Author",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Create notification preferences
    prefs = NotificationPreferences(
        user_id=user.id,
        email_notifications=True,
        forum_notifications=True,
        event_notifications=True,
        announcement_notifications=True
    )
    db_session.add(prefs)
    db_session.commit()
    
    return user


@pytest.fixture
def replier(db_session: Session):
    """Create a replier user"""
    user = User(
        email="replier@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Reply",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_topic(db_session: Session, topic_author: User):
    """Create a test topic"""
    topic = Topic(
        title="Test Topic for Notifications",
        author_id=topic_author.id,
        is_pinned=False,
        is_locked=False
    )
    db_session.add(topic)
    db_session.commit()
    db_session.refresh(topic)
    return topic


@patch('app.services.notification_service.email_service')
def test_forum_reply_sends_notification_to_topic_author(
    mock_email_service: Mock,
    db_session: Session,
    topic_author: User,
    replier: User,
    test_topic: Topic
):
    """Test that creating a post sends notification to topic author
    
    Validates Requirement 10.2:
    - Sends email notification when member receives forum reply
    """
    # Setup mock
    mock_email_service.send_email.return_value = True
    
    # Create access token for replier
    token = create_access_token({"sub": str(replier.id)})
    
    # Create test client
    client = TestClient(app)
    
    # Create a post (reply) to the topic
    response = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json={"content": "This is a test reply"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify post was created successfully
    assert response.status_code == 201
    
    # Verify notification email was sent
    mock_email_service.send_email.assert_called_once()
    
    # Verify email was sent to topic author
    call_args = mock_email_service.send_email.call_args
    assert call_args.kwargs['to_email'] == topic_author.email
    assert "Test Topic for Notifications" in call_args.kwargs['subject']
    assert "Reply User" in call_args.kwargs['body_text']


@patch('app.services.notification_service.email_service')
def test_forum_reply_does_not_notify_self(
    mock_email_service: Mock,
    db_session: Session,
    topic_author: User,
    test_topic: Topic
):
    """Test that replying to own topic does not send notification
    
    Validates Requirement 10.2:
    - Should not send notification when user replies to their own topic
    """
    # Setup mock
    mock_email_service.send_email.return_value = True
    
    # Create access token for topic author
    token = create_access_token({"sub": str(topic_author.id)})
    
    # Create test client
    client = TestClient(app)
    
    # Create a post (reply) to own topic
    response = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json={"content": "Replying to my own topic"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify post was created successfully
    assert response.status_code == 201
    
    # Verify NO notification email was sent (user replying to own topic)
    mock_email_service.send_email.assert_not_called()


@patch('app.services.notification_service.email_service')
def test_forum_reply_respects_notification_preferences(
    mock_email_service: Mock,
    db_session: Session,
    topic_author: User,
    replier: User,
    test_topic: Topic
):
    """Test that forum reply notifications respect user preferences
    
    Validates Requirement 10.4:
    - Checks user preferences before sending notifications
    """
    # Disable forum notifications for topic author
    prefs = db_session.query(NotificationPreferences).filter(
        NotificationPreferences.user_id == topic_author.id
    ).first()
    prefs.forum_notifications = False
    db_session.commit()
    
    # Setup mock
    mock_email_service.send_email.return_value = True
    
    # Create access token for replier
    token = create_access_token({"sub": str(replier.id)})
    
    # Create test client
    client = TestClient(app)
    
    # Create a post (reply) to the topic
    response = client.post(
        f"/api/forum/topics/{test_topic.id}/posts",
        json={"content": "This is a test reply"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify post was created successfully
    assert response.status_code == 201
    
    # Verify NO notification email was sent (preferences disabled)
    mock_email_service.send_email.assert_not_called()

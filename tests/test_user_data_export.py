"""Tests for personal data export endpoint

Validates Requirement 9.7:
- Members can download their personal data
- Export includes all relevant data categories
- Complies with RGPD data portability requirements
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from app.models import (
    User, UserRole, Topic, Post, Payment, PaymentMethod, PaymentStatus,
    Event, EventRegistration, EventStatus
)
from app.auth.token import create_access_token


def test_export_user_data_success(client: TestClient, db_session: Session, test_user: User):
    """Test successful export of user data
    
    Validates Requirement 9.7:
    - Authenticated user can export their personal data
    - Export includes profile, forum activity, payments, and event registrations
    """
    # Create some test data for the user
    
    # Forum topic
    topic = Topic(
        title="Test Topic",
        author_id=test_user.id,
        is_pinned=False,
        is_locked=False
    )
    db_session.add(topic)
    db_session.flush()
    
    # Forum post
    post = Post(
        topic_id=topic.id,
        author_id=test_user.id,
        content="Test post content",
        is_hidden=False
    )
    db_session.add(post)
    
    # Payment
    payment = Payment(
        user_id=test_user.id,
        amount=Decimal("50.00"),
        currency="EUR",
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.COMPLETED,
        transaction_id="test_txn_123",
        invoice_url="/storage/invoices/test_invoice.pdf"
    )
    db_session.add(payment)
    
    # Event and registration
    event = Event(
        title="Test Event",
        description="Test event description",
        start_date=datetime.now(timezone.utc) + timedelta(days=7),
        end_date=datetime.now(timezone.utc) + timedelta(days=7, hours=2),
        location="Test Location",
        created_by=test_user.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.flush()
    
    registration = EventRegistration(
        event_id=event.id,
        user_id=test_user.id,
        attended=None
    )
    db_session.add(registration)
    db_session.commit()
    
    # Generate token for authentication
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value
        }
    )
    
    # Make request to export endpoint
    response = client.get(
        "/api/users/me/export",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    
    # Verify profile data
    assert "profile" in data
    assert data["profile"]["email"] == test_user.email
    assert data["profile"]["first_name"] == test_user.first_name
    assert data["profile"]["last_name"] == test_user.last_name
    assert data["profile"]["role"] == test_user.role.value
    assert data["profile"]["is_email_verified"] == test_user.is_email_verified
    
    # Verify forum topics
    assert "forum_topics" in data
    assert len(data["forum_topics"]) == 1
    assert data["forum_topics"][0]["title"] == "Test Topic"
    assert data["forum_topics"][0]["is_pinned"] == False
    
    # Verify forum posts
    assert "forum_posts" in data
    assert len(data["forum_posts"]) == 1
    assert data["forum_posts"][0]["content"] == "Test post content"
    assert data["forum_posts"][0]["is_hidden"] == False
    
    # Verify payments
    assert "payments" in data
    assert len(data["payments"]) == 1
    assert data["payments"][0]["amount"] == 50.00
    assert data["payments"][0]["currency"] == "EUR"
    assert data["payments"][0]["payment_method"] == "credit_card"
    assert data["payments"][0]["status"] == "completed"
    assert data["payments"][0]["transaction_id"] == "test_txn_123"
    
    # Verify event registrations
    assert "event_registrations" in data
    assert len(data["event_registrations"]) == 1
    assert data["event_registrations"][0]["event_title"] == "Test Event"
    assert data["event_registrations"][0]["event_location"] == "Test Location"
    assert data["event_registrations"][0]["attended"] is None


def test_export_user_data_empty(client: TestClient, db_session: Session, test_user: User):
    """Test export for user with no activity
    
    Validates Requirement 9.7:
    - Export works even when user has no forum posts, payments, or registrations
    - Returns empty lists for each category
    """
    # Generate token for authentication
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value
        }
    )
    
    # Make request to export endpoint
    response = client.get(
        "/api/users/me/export",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    
    # Verify profile data exists
    assert "profile" in data
    assert data["profile"]["email"] == test_user.email
    
    # Verify empty lists for activity
    assert "forum_topics" in data
    assert len(data["forum_topics"]) == 0
    
    assert "forum_posts" in data
    assert len(data["forum_posts"]) == 0
    
    assert "payments" in data
    assert len(data["payments"]) == 0
    
    assert "event_registrations" in data
    assert len(data["event_registrations"]) == 0


def test_export_user_data_unauthorized(client: TestClient, db_session: Session):
    """Test export without authentication
    
    Validates Requirement 9.7:
    - Only authenticated users can export their data
    - Unauthenticated requests are rejected
    """
    # Make request without token
    response = client.get("/api/users/me/export")
    
    # Verify unauthorized response
    assert response.status_code == 403  # FastAPI HTTPBearer returns 403 for missing credentials


def test_export_user_data_invalid_token(client: TestClient, db_session: Session):
    """Test export with invalid token
    
    Validates Requirement 9.7:
    - Invalid tokens are rejected
    - User must have valid authentication
    """
    # Make request with invalid token
    response = client.get(
        "/api/users/me/export",
        headers={"Authorization": "Bearer invalid_token_here"}
    )
    
    # Verify unauthorized response
    assert response.status_code == 401


def test_export_user_data_only_own_data(client: TestClient, db_session: Session, test_user: User):
    """Test that users can only export their own data
    
    Validates Requirement 9.7:
    - Users can only access their own personal data
    - Data from other users is not included in export
    """
    # Create another user with data
    other_user = User(
        email="other@example.com",
        password_hash="hashed_password",
        first_name="Other",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(other_user)
    db_session.flush()
    
    # Create data for other user
    other_topic = Topic(
        title="Other User Topic",
        author_id=other_user.id,
        is_pinned=False,
        is_locked=False
    )
    db_session.add(other_topic)
    
    other_payment = Payment(
        user_id=other_user.id,
        amount=Decimal("100.00"),
        currency="EUR",
        payment_method=PaymentMethod.PAYPAL,
        status=PaymentStatus.COMPLETED,
        transaction_id="other_txn_456"
    )
    db_session.add(other_payment)
    db_session.commit()
    
    # Generate token for test_user
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value
        }
    )
    
    # Make request to export endpoint
    response = client.get(
        "/api/users/me/export",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    
    # Verify only test_user's data is included
    assert data["profile"]["email"] == test_user.email
    assert len(data["forum_topics"]) == 0  # test_user has no topics
    assert len(data["payments"]) == 0  # test_user has no payments
    
    # Verify other user's data is NOT included
    for topic in data["forum_topics"]:
        assert topic["title"] != "Other User Topic"
    
    for payment in data["payments"]:
        assert payment["transaction_id"] != "other_txn_456"


def test_export_includes_all_timestamps(client: TestClient, db_session: Session, test_user: User):
    """Test that export includes all timestamp fields
    
    Validates Requirement 9.7:
    - Export includes complete temporal information
    - All created_at and updated_at fields are present
    """
    # Create a topic
    topic = Topic(
        title="Timestamped Topic",
        author_id=test_user.id,
        is_pinned=False,
        is_locked=False
    )
    db_session.add(topic)
    db_session.commit()
    
    # Generate token
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value
        }
    )
    
    # Make request
    response = client.get(
        "/api/users/me/export",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    
    # Verify profile timestamps
    assert "created_at" in data["profile"]
    assert "updated_at" in data["profile"]
    
    # Verify topic timestamps
    assert len(data["forum_topics"]) == 1
    assert "created_at" in data["forum_topics"][0]
    assert "updated_at" in data["forum_topics"][0]


def test_export_includes_membership_expiration(client: TestClient, db_session: Session, test_user: User):
    """Test that export includes membership expiration date
    
    Validates Requirement 9.7:
    - Export includes membership status information
    - Membership expiration date is included when set
    """
    # Set membership expiration
    test_user.membership_expires_at = datetime.now(timezone.utc) + timedelta(days=365)
    db_session.commit()
    
    # Generate token
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value
        }
    )
    
    # Make request
    response = client.get(
        "/api/users/me/export",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    
    # Verify membership expiration is included
    assert "membership_expires_at" in data["profile"]
    assert data["profile"]["membership_expires_at"] is not None

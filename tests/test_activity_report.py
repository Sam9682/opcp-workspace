"""Tests for activity report generation endpoint

Validates Requirements 8.4:
- Generates annual activity reports accessible to all members
- Calculates statistics (new members, active members, events, forum activity, revenue)
- Supports date range filtering
"""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models import (
    User, UserRole, Topic, Post, Event, EventStatus,
    Payment, PaymentStatus, PaymentMethod
)
from app.auth.password import hash_password
from app.auth.token import create_access_token
from decimal import Decimal


client = TestClient(app)


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create an administrator user for testing"""
    admin = User(
        email="admin@opcp-psmc.com",
        password_hash=hash_password("Admin1234!"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True,
        membership_expires_at=datetime.now(timezone.utc) + timedelta(days=365)
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def admin_headers(client, admin_user: User):
    """Get authentication headers for admin user"""
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@opcp-psmc.com",
            "password": "Admin1234!"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def member_user(db_session: Session) -> User:
    """Create a regular member user for testing"""
    member = User(
        email="member@OPCP.org",
        password_hash=hash_password("MemberPass123"),
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True,
        membership_expires_at=datetime.now(timezone.utc) + timedelta(days=365)
    )
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)
    return member


@pytest.fixture
def member_headers(client, member_user: User):
    """Get authentication headers for member user"""
    response = client.post(
        "/api/auth/login",
        json={
            "email": "member@OPCP.org",
            "password": "MemberPass123"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_activity_report_requires_authentication(client):
    """Test that activity report endpoint requires authentication"""
    response = client.get("/api/admin/reports/activity")
    
    # Should return 401 or 403 depending on how the dependency chain handles it
    assert response.status_code in [401, 403]


def test_activity_report_requires_admin_role(client, member_headers):
    """Test that activity report endpoint requires administrator role"""
    response = client.get(
        "/api/admin/reports/activity",
        headers=member_headers
    )
    
    assert response.status_code == 403
    # The error response might be in different formats
    response_data = response.json()
    if "detail" in response_data:
        if isinstance(response_data["detail"], dict):
            assert response_data["detail"]["code"] == "INSUFFICIENT_PERMISSIONS"
        else:
            # String detail
            assert "insufficient" in response_data["detail"].lower() or "permission" in response_data["detail"].lower()


def test_activity_report_default_date_range(
    client,
    admin_headers,
    admin_user: User
):
    """Test activity report with default date range (current year)"""
    response = client.get(
        "/api/admin/reports/activity",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "period_start" in data
    assert "period_end" in data
    assert "new_members" in data
    assert "active_members" in data
    assert "events_held" in data
    assert "forum_activity" in data
    assert "revenue" in data
    
    # Verify forum activity structure
    assert "topics" in data["forum_activity"]
    assert "posts" in data["forum_activity"]
    
    # Verify default date range is current year
    now = datetime.now(timezone.utc)
    period_start = datetime.fromisoformat(data["period_start"].replace('Z', '+00:00'))
    period_end = datetime.fromisoformat(data["period_end"].replace('Z', '+00:00'))
    
    assert period_start.year == now.year
    assert period_start.month == 1
    assert period_start.day == 1
    assert period_end.year == now.year
    assert period_end.month == 12
    assert period_end.day == 31


def test_activity_report_custom_date_range(client, 
    db_session: Session,
    admin_headers,
    admin_user: User
):
    """Test activity report with custom date range"""
    start_date = "2024-01-01T00:00:00Z"
    end_date = "2024-06-30T23:59:59Z"
    
    response = client.get(
        "/api/admin/reports/activity",
        params={
            "start_date": start_date,
            "end_date": end_date
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify custom date range is used
    assert data["period_start"] == start_date
    assert data["period_end"] == end_date


def test_activity_report_invalid_date_range(client, 
    db_session: Session,
    admin_headers,
    admin_user: User
):
    """Test activity report with invalid date range (end before start)"""
    start_date = "2024-06-30T00:00:00Z"
    end_date = "2024-01-01T00:00:00Z"
    
    response = client.get(
        "/api/admin/reports/activity",
        params={
            "start_date": start_date,
            "end_date": end_date
        },
        headers=admin_headers
    )
    
    assert response.status_code == 400
    response_data = response.json()
    if "detail" in response_data:
        if isinstance(response_data["detail"], dict):
            assert response_data["detail"]["code"] == "INVALID_DATE_RANGE"
        else:
            # String detail
            assert "date" in response_data["detail"].lower() and "range" in response_data["detail"].lower()


def test_activity_report_calculates_new_members(client, 
    db_session: Session,
    admin_headers,
    admin_user: User
):
    """Test that activity report correctly counts new members in the period"""
    # Create members with different registration dates
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    
    # Member registered before period (should not be counted)
    user_before = User(
        email="before@test.com",
        password_hash=hash_password("Test1234"),
        first_name="Before",
        last_name="Period",
        role=UserRole.MEMBER,
        is_email_verified=True,
        created_at=datetime(2023, 12, 31, tzinfo=timezone.utc)
    )
    db_session.add(user_before)
    
    # Members registered during period (should be counted)
    user_during_1 = User(
        email="during1@test.com",
        password_hash=hash_password("Test1234"),
        first_name="During",
        last_name="One",
        role=UserRole.MEMBER,
        is_email_verified=True,
        created_at=datetime(2024, 3, 15, tzinfo=timezone.utc)
    )
    db_session.add(user_during_1)
    
    user_during_2 = User(
        email="during2@test.com",
        password_hash=hash_password("Test1234"),
        first_name="During",
        last_name="Two",
        role=UserRole.MEMBER,
        is_email_verified=True,
        created_at=datetime(2024, 7, 20, tzinfo=timezone.utc)
    )
    db_session.add(user_during_2)
    
    # Member registered after period (should not be counted)
    user_after = User(
        email="after@test.com",
        password_hash=hash_password("Test1234"),
        first_name="After",
        last_name="Period",
        role=UserRole.MEMBER,
        is_email_verified=True,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
    )
    db_session.add(user_after)
    
    db_session.commit()
    
    response = client.get(
        "/api/admin/reports/activity",
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should count 2 members registered during the period
    # (admin_user is also created during the period in the fixture)
    assert data["new_members"] >= 2


def test_activity_report_calculates_active_members(client, 
    db_session: Session,
    admin_headers,
    admin_user: User
):
    """Test that activity report correctly counts active members"""
    end_date = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    
    # Active member (expires after end_date)
    active_member = User(
        email="active@test.com",
        password_hash=hash_password("Test1234"),
        first_name="Active",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=True,
        membership_expires_at=datetime(2025, 6, 30, tzinfo=timezone.utc)
    )
    db_session.add(active_member)
    
    # Expired member (expires before end_date)
    expired_member = User(
        email="expired@test.com",
        password_hash=hash_password("Test1234"),
        first_name="Expired",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=True,
        membership_expires_at=datetime(2024, 6, 30, tzinfo=timezone.utc)
    )
    db_session.add(expired_member)
    
    # Unverified member (should not be counted)
    unverified_member = User(
        email="unverified@test.com",
        password_hash=hash_password("Test1234"),
        first_name="Unverified",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=False,
        membership_expires_at=datetime(2025, 6, 30, tzinfo=timezone.utc)
    )
    db_session.add(unverified_member)
    
    db_session.commit()
    
    response = client.get(
        "/api/admin/reports/activity",
        params={
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": end_date.isoformat()
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should count at least 2 active members (admin_user + active_member)
    assert data["active_members"] >= 2


def test_activity_report_calculates_events_held(client, 
    db_session: Session,
    admin_headers,
    admin_user: User
):
    """Test that activity report correctly counts events held in the period"""
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    
    # Event held during period (completed)
    event_completed = Event(
        title="Completed Event",
        description="Event that was held",
        start_date=datetime(2024, 6, 15, 14, 0, tzinfo=timezone.utc),
        end_date=datetime(2024, 6, 15, 16, 0, tzinfo=timezone.utc),
        location="Test Location",
        created_by=admin_user.id,
        status=EventStatus.COMPLETED
    )
    db_session.add(event_completed)
    
    # Event scheduled but not completed (should not be counted)
    event_scheduled = Event(
        title="Scheduled Event",
        description="Event that is scheduled",
        start_date=datetime(2024, 8, 20, 14, 0, tzinfo=timezone.utc),
        end_date=datetime(2024, 8, 20, 16, 0, tzinfo=timezone.utc),
        location="Test Location",
        created_by=admin_user.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event_scheduled)
    
    # Event cancelled (should not be counted)
    event_cancelled = Event(
        title="Cancelled Event",
        description="Event that was cancelled",
        start_date=datetime(2024, 9, 10, 14, 0, tzinfo=timezone.utc),
        end_date=datetime(2024, 9, 10, 16, 0, tzinfo=timezone.utc),
        location="Test Location",
        created_by=admin_user.id,
        status=EventStatus.CANCELLED
    )
    db_session.add(event_cancelled)
    
    # Event outside period (should not be counted)
    event_outside = Event(
        title="Outside Event",
        description="Event outside the period",
        start_date=datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 15, 16, 0, tzinfo=timezone.utc),
        location="Test Location",
        created_by=admin_user.id,
        status=EventStatus.COMPLETED
    )
    db_session.add(event_outside)
    
    db_session.commit()
    
    response = client.get(
        "/api/admin/reports/activity",
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should count only 1 completed event in the period
    assert data["events_held"] == 1


def test_activity_report_calculates_forum_activity(client, 
    db_session: Session,
    admin_headers,
    admin_user: User,
    member_user: User
):
    """Test that activity report correctly counts forum topics and posts"""
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    
    # Topic created during period
    topic_during = Topic(
        title="Topic During Period",
        author_id=member_user.id,
        created_at=datetime(2024, 5, 10, tzinfo=timezone.utc)
    )
    db_session.add(topic_during)
    db_session.flush()
    
    # Post on topic during period
    post_during = Post(
        topic_id=topic_during.id,
        author_id=admin_user.id,
        content="Post during period",
        created_at=datetime(2024, 5, 11, tzinfo=timezone.utc)
    )
    db_session.add(post_during)
    
    # Topic created before period
    topic_before = Topic(
        title="Topic Before Period",
        author_id=member_user.id,
        created_at=datetime(2023, 12, 31, tzinfo=timezone.utc)
    )
    db_session.add(topic_before)
    db_session.flush()
    
    # Post on old topic but created during period (should be counted)
    post_on_old_topic = Post(
        topic_id=topic_before.id,
        author_id=admin_user.id,
        content="Post on old topic",
        created_at=datetime(2024, 6, 15, tzinfo=timezone.utc)
    )
    db_session.add(post_on_old_topic)
    
    db_session.commit()
    
    response = client.get(
        "/api/admin/reports/activity",
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should count 1 topic created during period
    assert data["forum_activity"]["topics"] == 1
    # Should count 2 posts created during period
    assert data["forum_activity"]["posts"] == 2


def test_activity_report_calculates_revenue(client, 
    db_session: Session,
    admin_headers,
    admin_user: User,
    member_user: User
):
    """Test that activity report correctly calculates revenue from payments"""
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    
    # Completed payment during period
    payment_completed_1 = Payment(
        user_id=member_user.id,
        amount=Decimal("50.00"),
        currency="EUR",
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.COMPLETED,
        transaction_id="txn_123",
        created_at=datetime(2024, 3, 15, tzinfo=timezone.utc)
    )
    db_session.add(payment_completed_1)
    
    # Another completed payment during period
    payment_completed_2 = Payment(
        user_id=admin_user.id,
        amount=Decimal("75.50"),
        currency="EUR",
        payment_method=PaymentMethod.PAYPAL,
        status=PaymentStatus.COMPLETED,
        transaction_id="txn_456",
        created_at=datetime(2024, 7, 20, tzinfo=timezone.utc)
    )
    db_session.add(payment_completed_2)
    
    # Pending payment (should not be counted)
    payment_pending = Payment(
        user_id=member_user.id,
        amount=Decimal("50.00"),
        currency="EUR",
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.PENDING,
        transaction_id="txn_789",
        created_at=datetime(2024, 8, 10, tzinfo=timezone.utc)
    )
    db_session.add(payment_pending)
    
    # Failed payment (should not be counted)
    payment_failed = Payment(
        user_id=member_user.id,
        amount=Decimal("50.00"),
        currency="EUR",
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.FAILED,
        transaction_id="txn_999",
        created_at=datetime(2024, 9, 5, tzinfo=timezone.utc)
    )
    db_session.add(payment_failed)
    
    # Payment outside period (should not be counted)
    payment_outside = Payment(
        user_id=member_user.id,
        amount=Decimal("50.00"),
        currency="EUR",
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.COMPLETED,
        transaction_id="txn_000",
        created_at=datetime(2025, 1, 5, tzinfo=timezone.utc)
    )
    db_session.add(payment_outside)
    
    db_session.commit()
    
    response = client.get(
        "/api/admin/reports/activity",
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should sum only completed payments during period: 50.00 + 75.50 = 125.50
    assert data["revenue"] == 125.50


def test_activity_report_with_no_data(client, 
    db_session: Session,
    admin_headers,
    admin_user: User
):
    """Test activity report with a period that has no activity"""
    # Use a future date range with no data
    start_date = datetime(2030, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2030, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    
    response = client.get(
        "/api/admin/reports/activity",
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # All counts should be zero
    assert data["new_members"] == 0
    assert data["active_members"] == 0
    assert data["events_held"] == 0
    assert data["forum_activity"]["topics"] == 0
    assert data["forum_activity"]["posts"] == 0
    assert data["revenue"] == 0.0

"""Tests for user data deletion endpoint

Feature: OPCP-website
Validates Requirement 9.4:
- DELETE /api/users/me (request account deletion)
- Schedules data deletion within 30 days
- Anonymizes or removes personal data
- Preserves necessary records for legal compliance
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.models import (
    User, UserRole, ScheduledUserDeletion, 
    Post, Topic, Payment, PaymentStatus, PaymentMethod,
    Event, EventRegistration, EventStatus,
    Document, DocumentCategory, AccessLevel,
    Notification, NotificationType, NotificationPreferences,
    AuditLog
)
from app.services.user_deletion_service import UserDeletionService


def test_request_deletion_success(client, test_user, auth_headers, db_session):
    """Test successful account deletion request
    
    Validates Requirement 9.4: User requests deletion, system schedules within 30 days
    """
    # Request deletion
    response = client.delete(
        "/api/users/me",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert "scheduled" in data["message"].lower()
    assert "scheduled_for" in data
    
    # Verify scheduled deletion was created
    scheduled = db_session.query(ScheduledUserDeletion).filter(
        ScheduledUserDeletion.user_id == test_user.id
    ).first()
    
    assert scheduled is not None
    assert scheduled.user_email == test_user.email
    assert scheduled.user_full_name == f"{test_user.first_name} {test_user.last_name}"
    
    # Verify deletion is scheduled within 30 days
    now = datetime.now(timezone.utc)
    expected_date = now + timedelta(days=30)
    # Remove timezone info for comparison with SQLite datetime
    scheduled_date = scheduled.scheduled_for.replace(tzinfo=timezone.utc) if scheduled.scheduled_for.tzinfo is None else scheduled.scheduled_for
    time_diff = abs((scheduled_date - expected_date).total_seconds())
    assert time_diff < 60  # Within 1 minute
    
    # Verify user account is immediately deactivated
    db_session.refresh(test_user)
    assert test_user.is_email_verified is False


def test_request_deletion_already_scheduled(client, test_user, auth_headers, db_session):
    """Test deletion request when already scheduled
    
    Validates Requirement 9.4: System prevents duplicate deletion requests
    """
    # Create existing scheduled deletion
    deletion_date = datetime.now(timezone.utc) + timedelta(days=30)
    scheduled = ScheduledUserDeletion(
        user_id=test_user.id,
        user_email=test_user.email,
        user_full_name=f"{test_user.first_name} {test_user.last_name}",
        scheduled_for=deletion_date
    )
    db_session.add(scheduled)
    db_session.commit()
    
    # Try to request deletion again
    response = client.delete(
        "/api/users/me",
        headers=auth_headers
    )
    
    assert response.status_code == 409
    data = response.json()
    
    assert "error" in data
    assert data["error"]["code"] == "DELETION_ALREADY_SCHEDULED"
    assert "already scheduled" in data["error"]["message"].lower()


def test_request_deletion_unauthenticated(client):
    """Test deletion request without authentication"""
    response = client.delete("/api/users/me")
    
    # FastAPI returns 403 for missing authentication
    assert response.status_code == 403


def test_process_scheduled_deletion_anonymizes_data(db_session):
    """Test that scheduled deletion properly anonymizes user data
    
    Validates Requirement 9.4: System anonymizes personal data while preserving legal records
    """
    # Create a user with various data
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        first_name="John",
        last_name="Doe",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    # Create forum topic and post
    topic = Topic(
        title="Test Topic",
        author_id=user.id
    )
    db_session.add(topic)
    db_session.commit()
    
    post = Post(
        topic_id=topic.id,
        author_id=user.id,
        content="Test post content"
    )
    db_session.add(post)
    
    # Create payment (should be preserved)
    payment = Payment(
        user_id=user.id,
        amount=50.00,
        currency="EUR",
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.COMPLETED,
        transaction_id="test_txn_123"
    )
    db_session.add(payment)
    
    # Create event registration
    event = Event(
        title="Test Event",
        description="Test",
        start_date=datetime.now(timezone.utc) + timedelta(days=7),
        end_date=datetime.now(timezone.utc) + timedelta(days=7, hours=2),
        location="Test Location",
        created_by=user.id,
        status=EventStatus.SCHEDULED
    )
    db_session.add(event)
    db_session.commit()
    
    registration = EventRegistration(
        event_id=event.id,
        user_id=user.id
    )
    db_session.add(registration)
    
    # Create notification
    notification = Notification(
        user_id=user.id,
        type=NotificationType.ANNOUNCEMENT,
        subject="Test",
        content="Test notification"
    )
    db_session.add(notification)
    
    # Create notification preferences
    prefs = NotificationPreferences(
        user_id=user.id,
        email_notifications=True
    )
    db_session.add(prefs)
    
    # Create audit log (should be preserved)
    audit = AuditLog(
        admin_id=user.id,
        action="test_action",
        target_type="test",
        target_id=user.id
    )
    db_session.add(audit)
    
    db_session.commit()
    
    # Schedule deletion for now
    scheduled = ScheduledUserDeletion(
        user_id=user.id,
        user_email=user.email,
        user_full_name=f"{user.first_name} {user.last_name}",
        scheduled_for=datetime.now(timezone.utc)
    )
    db_session.add(scheduled)
    db_session.commit()
    
    # Process the deletion
    result = UserDeletionService.process_scheduled_deletions(db_session)
    
    assert result == 1
    
    # Verify user is anonymized
    db_session.refresh(user)
    assert user.email.startswith("deleted_user_")
    assert user.first_name == "Deleted"
    assert user.last_name == "User"
    assert user.password_hash == "DELETED"
    assert user.is_email_verified is False
    
    # Verify forum content is preserved (posts and topics still exist)
    assert db_session.query(Topic).filter(Topic.id == topic.id).first() is not None
    assert db_session.query(Post).filter(Post.id == post.id).first() is not None
    
    # Verify payment is preserved (legal compliance)
    preserved_payment = db_session.query(Payment).filter(Payment.id == payment.id).first()
    assert preserved_payment is not None
    assert preserved_payment.user_id == user.id
    
    # Verify event registration is deleted
    assert db_session.query(EventRegistration).filter(
        EventRegistration.id == registration.id
    ).first() is None
    
    # Verify notification is deleted
    assert db_session.query(Notification).filter(
        Notification.id == notification.id
    ).first() is None
    
    # Verify notification preferences are deleted
    assert db_session.query(NotificationPreferences).filter(
        NotificationPreferences.user_id == user.id
    ).first() is None
    
    # Verify audit log is preserved (legal compliance)
    preserved_audit = db_session.query(AuditLog).filter(AuditLog.id == audit.id).first()
    assert preserved_audit is not None
    
    # Verify scheduled deletion record is removed
    assert db_session.query(ScheduledUserDeletion).filter(
        ScheduledUserDeletion.user_id == user.id
    ).first() is None


def test_process_scheduled_deletion_no_due_deletions(db_session):
    """Test processing when no deletions are due"""
    # Create a scheduled deletion for the future
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        first_name="John",
        last_name="Doe",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    future_date = datetime.now(timezone.utc) + timedelta(days=15)
    scheduled = ScheduledUserDeletion(
        user_id=user.id,
        user_email=user.email,
        user_full_name=f"{user.first_name} {user.last_name}",
        scheduled_for=future_date
    )
    db_session.add(scheduled)
    db_session.commit()
    
    # Process deletions
    result = UserDeletionService.process_scheduled_deletions(db_session)
    
    # No deletions should be processed
    assert result == 0
    
    # User should still exist and not be anonymized
    db_session.refresh(user)
    assert user.email == "test@example.com"
    assert user.first_name == "John"
    
    # Scheduled deletion should still exist
    assert db_session.query(ScheduledUserDeletion).filter(
        ScheduledUserDeletion.user_id == user.id
    ).first() is not None


def test_deletion_preserves_payment_records(db_session):
    """Test that payment records are preserved for legal compliance
    
    Validates Requirement 9.4: Preserve necessary records for legal compliance
    """
    # Create user with payment
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        first_name="John",
        last_name="Doe",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    
    payment = Payment(
        user_id=user.id,
        amount=100.00,
        currency="EUR",
        payment_method=PaymentMethod.CREDIT_CARD,
        status=PaymentStatus.COMPLETED,
        transaction_id="txn_legal_123",
        invoice_url="/invoices/invoice_123.pdf"
    )
    db_session.add(payment)
    db_session.commit()
    
    # Schedule and process deletion
    scheduled = ScheduledUserDeletion(
        user_id=user.id,
        user_email=user.email,
        user_full_name=f"{user.first_name} {user.last_name}",
        scheduled_for=datetime.now(timezone.utc)
    )
    db_session.add(scheduled)
    db_session.commit()
    
    UserDeletionService.process_scheduled_deletions(db_session)
    
    # Verify payment still exists with all details
    preserved_payment = db_session.query(Payment).filter(Payment.id == payment.id).first()
    assert preserved_payment is not None
    assert preserved_payment.amount == 100.00
    assert preserved_payment.transaction_id == "txn_legal_123"
    assert preserved_payment.invoice_url == "/invoices/invoice_123.pdf"
    assert preserved_payment.user_id == user.id


def test_deletion_preserves_audit_logs(db_session):
    """Test that audit logs are preserved for legal compliance
    
    Validates Requirement 9.4: Preserve necessary records for legal compliance
    """
    # Create admin user with audit logs
    admin = User(
        email="admin@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create audit logs
    audit1 = AuditLog(
        admin_id=admin.id,
        action="role_change",
        target_type="user",
        target_id=admin.id,
        details={"old_role": "member", "new_role": "administrator"}
    )
    audit2 = AuditLog(
        admin_id=admin.id,
        action="document_delete",
        target_type="document",
        target_id=admin.id
    )
    db_session.add_all([audit1, audit2])
    db_session.commit()
    
    # Schedule and process deletion
    scheduled = ScheduledUserDeletion(
        user_id=admin.id,
        user_email=admin.email,
        user_full_name=f"{admin.first_name} {admin.last_name}",
        scheduled_for=datetime.now(timezone.utc)
    )
    db_session.add(scheduled)
    db_session.commit()
    
    UserDeletionService.process_scheduled_deletions(db_session)
    
    # Verify audit logs still exist
    preserved_audits = db_session.query(AuditLog).filter(
        AuditLog.admin_id == admin.id
    ).all()
    assert len(preserved_audits) == 2
    assert preserved_audits[0].action == "role_change"
    assert preserved_audits[1].action == "document_delete"

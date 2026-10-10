"""Tests for announcement endpoint
Feature: OPCP-website
Validates Requirement 10.5
"""
import pytest
from unittest.mock import patch, Mock
from app.models import User, UserRole, NotificationPreferences, AuditLog
from app.auth.password import hash_password


@pytest.fixture
def admin_user(db_session):
    """Create an administrator user for testing"""
    user = User(
        email="admin@test.com",
        password_hash=hash_password("Admin1234"),
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
def member_user(db_session):
    """Create a regular member user for testing"""
    user = User(
        email="member@test.com",
        password_hash=hash_password("Member1234"),
        first_name="Member",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(client, admin_user):
    """Get authentication headers for admin user"""
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@test.com",
            "password": "Admin1234"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def member_headers(client, member_user):
    """Get authentication headers for member user"""
    response = client.post(
        "/api/auth/login",
        json={
            "email": "member@test.com",
            "password": "Member1234"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def active_members(db_session):
    """Create multiple active members for testing"""
    members = []
    for i in range(3):
        user = User(
            email=f"member{i}@test.com",
            password_hash=hash_password("Member1234"),
            first_name=f"Member{i}",
            last_name="User",
            role=UserRole.MEMBER,
            is_email_verified=True
        )
        db_session.add(user)
        members.append(user)
    
    db_session.commit()
    for member in members:
        db_session.refresh(member)
    return members


@patch('app.services.email_service.email_service.send_email')
def test_send_announcement_success(
    mock_send_email: Mock,
    client,
    admin_headers,
    admin_user,
    active_members,
    db_session
):
    """Test administrator can successfully send announcement to all active members
    
    Validates Requirement 10.5:
    - Administrator sends announcement to all active members by email
    """
    # Mock email service to return success
    mock_send_email.return_value = True
    
    # Send announcement
    response = client.post(
        "/api/admin/announcements",
        json={
            "subject": "Important Announcement",
            "content": "This is an important announcement for all members.",
            "sender_name": "OPCP"
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response
    assert data["success"] is True
    assert "sent successfully" in data["message"]
    assert data["notifications_sent"] == 4  # 3 members + 1 admin
    assert data["total_members"] == 4
    
    # Verify email service was called for each member
    assert mock_send_email.call_count == 4
    
    # Verify audit log entry
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "send_announcement",
        AuditLog.admin_id == admin_user.id
    ).first()
    
    assert audit_entry is not None
    assert audit_entry.target_type == "announcement"
    assert audit_entry.details["subject"] == "Important Announcement"
    assert audit_entry.details["notifications_sent"] == 4
    assert audit_entry.details["total_active_members"] == 4


@patch('app.services.email_service.email_service.send_email')
def test_send_announcement_respects_preferences(
    mock_send_email: Mock,
    client,
    admin_headers,
    admin_user,
    active_members,
    db_session
):
    """Test announcement respects user notification preferences
    
    Validates Requirements 10.4, 10.5:
    - Respects user notification preferences
    - Only sends to members with announcement notifications enabled
    """
    # Mock email service
    mock_send_email.return_value = True
    
    # Disable announcement notifications for one member
    prefs = NotificationPreferences(
        user_id=active_members[0].id,
        email_notifications=True,
        forum_notifications=True,
        event_notifications=True,
        announcement_notifications=False  # Disabled
    )
    db_session.add(prefs)
    db_session.commit()
    
    # Send announcement
    response = client.post(
        "/api/admin/announcements",
        json={
            "subject": "Test Announcement",
            "content": "Testing preferences",
            "sender_name": "OPCP"
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should send to 3 members (2 with default prefs + 1 admin), not the one who disabled
    assert data["notifications_sent"] == 3
    assert data["total_members"] == 4


@patch('app.services.email_service.email_service.send_email')
def test_send_announcement_non_admin_forbidden(
    mock_send_email: Mock,
    client,
    member_headers
):
    """Test non-administrator cannot send announcements
    
    Validates Requirement 7.2:
    - Administrative functions restricted to administrator role
    """
    response = client.post(
        "/api/admin/announcements",
        json={
            "subject": "Unauthorized Announcement",
            "content": "This should not be sent",
            "sender_name": "OPCP"
        },
        headers=member_headers
    )
    
    assert response.status_code == 403
    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "INSUFFICIENT_PERMISSIONS"
    
    # Verify email service was never called
    mock_send_email.assert_not_called()


@patch('app.services.email_service.email_service.send_email')
def test_send_announcement_unauthenticated_denied(
    mock_send_email: Mock,
    client
):
    """Test unauthenticated users cannot send announcements"""
    response = client.post(
        "/api/admin/announcements",
        json={
            "subject": "Unauthorized Announcement",
            "content": "This should not be sent",
            "sender_name": "OPCP"
        }
    )
    
    # The endpoint returns 403 because the dependency check happens first
    assert response.status_code == 403
    
    # Verify email service was never called
    mock_send_email.assert_not_called()


@patch('app.services.email_service.email_service.send_email')
def test_send_announcement_validation_errors(
    mock_send_email: Mock,
    client,
    admin_headers
):
    """Test announcement validation errors"""
    # Empty subject
    response = client.post(
        "/api/admin/announcements",
        json={
            "subject": "",
            "content": "Valid content",
            "sender_name": "OPCP"
        },
        headers=admin_headers
    )
    # Pydantic validation returns 400 in this app
    assert response.status_code == 400
    
    # Empty content
    response = client.post(
        "/api/admin/announcements",
        json={
            "subject": "Valid subject",
            "content": "",
            "sender_name": "OPCP"
        },
        headers=admin_headers
    )
    assert response.status_code == 400
    
    # Missing required fields
    response = client.post(
        "/api/admin/announcements",
        json={
            "subject": "Valid subject"
            # Missing content
        },
        headers=admin_headers
    )
    assert response.status_code == 400
    
    # Verify email service was never called
    mock_send_email.assert_not_called()


@patch('app.services.email_service.email_service.send_email')
def test_send_announcement_only_to_verified_members(
    mock_send_email: Mock,
    client,
    admin_headers,
    db_session
):
    """Test announcements only sent to verified members
    
    Validates Requirement 10.5:
    - Only sends to members with verified email
    """
    # Mock email service
    mock_send_email.return_value = True
    
    # Create verified and unverified members
    verified_member = User(
        email="verified@test.com",
        password_hash=hash_password("Member1234"),
        first_name="Verified",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    
    unverified_member = User(
        email="unverified@test.com",
        password_hash=hash_password("Member1234"),
        first_name="Unverified",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=False  # Not verified
    )
    
    db_session.add(verified_member)
    db_session.add(unverified_member)
    db_session.commit()
    
    # Send announcement
    response = client.post(
        "/api/admin/announcements",
        json={
            "subject": "Test Announcement",
            "content": "Testing verification",
            "sender_name": "OPCP"
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should send to 2 members (1 verified member + 1 admin), not the unverified one
    assert data["notifications_sent"] == 2
    assert data["total_members"] == 2


@patch('app.services.email_service.email_service.send_email')
def test_send_announcement_custom_sender_name(
    mock_send_email: Mock,
    client,
    admin_headers,
    admin_user,
    db_session
):
    """Test announcement with custom sender name"""
    # Mock email service
    mock_send_email.return_value = True
    
    # Send announcement with custom sender
    response = client.post(
        "/api/admin/announcements",
        json={
            "subject": "Custom Sender Test",
            "content": "Testing custom sender name",
            "sender_name": "Le Président"
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    # Verify audit log includes custom sender name
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "send_announcement",
        AuditLog.admin_id == admin_user.id
    ).first()
    
    assert audit_entry is not None
    assert audit_entry.details["sender_name"] == "Le Président"


@patch('app.services.email_service.email_service.send_email')
def test_send_announcement_default_sender_name(
    mock_send_email: Mock,
    client,
    admin_headers,
    admin_user,
    db_session
):
    """Test announcement uses default sender name when not provided"""
    # Mock email service
    mock_send_email.return_value = True
    
    # Send announcement without sender_name
    response = client.post(
        "/api/admin/announcements",
        json={
            "subject": "Default Sender Test",
            "content": "Testing default sender name"
            # No sender_name provided
        },
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    # Verify audit log uses default sender name
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "send_announcement",
        AuditLog.admin_id == admin_user.id
    ).first()
    
    assert audit_entry is not None
    assert audit_entry.details["sender_name"] == "OPCP"

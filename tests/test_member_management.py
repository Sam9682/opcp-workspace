"""Tests for member management endpoints
Feature: OPCP-website
Validates Requirements 7.3, 7.4
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.models import User, UserRole, AuditLog
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
        is_email_verified=True,
        membership_expires_at=datetime.now(timezone.utc) + timedelta(days=365)
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def expired_member(db_session):
    """Create a member with expired membership"""
    user = User(
        email="expired@test.com",
        password_hash=hash_password("Expired1234"),
        first_name="Expired",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=True,
        membership_expires_at=datetime.now(timezone.utc) - timedelta(days=30)
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def unverified_member(db_session):
    """Create an unverified member"""
    user = User(
        email="unverified@test.com",
        password_hash=hash_password("Unverified1234"),
        first_name="Unverified",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=False
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


# Tests for GET /api/admin/members

def test_list_members_success(client, admin_headers, admin_user, member_user, db_session):
    """Test administrator can list all members
    
    Validates Requirement 7.3:
    - Administrator views all members with roles and membership status
    """
    response = client.get(
        "/api/admin/members",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "members" in data
    assert "total" in data
    assert data["total"] == 2  # admin + member
    
    # Verify member data includes required fields
    members = data["members"]
    assert len(members) == 2
    
    for member in members:
        assert "id" in member
        assert "email" in member
        assert "first_name" in member
        assert "last_name" in member
        assert "role" in member
        assert "is_email_verified" in member
        assert "membership_status" in member
        assert "created_at" in member


def test_list_members_includes_all_statuses(
    client, admin_headers, admin_user, member_user, expired_member, unverified_member
):
    """Test member list includes members with different statuses"""
    response = client.get(
        "/api/admin/members",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] == 4  # admin + member + expired + unverified
    
    # Find each member and verify their status
    members_by_email = {m["email"]: m for m in data["members"]}
    
    # Active member with valid membership
    assert members_by_email["member@test.com"]["membership_status"] == "active"
    
    # Expired member
    assert members_by_email["expired@test.com"]["membership_status"] == "expired"
    
    # Unverified member (suspended)
    assert members_by_email["unverified@test.com"]["membership_status"] == "suspended"


def test_list_members_ordered_by_created_at(
    client, admin_headers, admin_user, member_user, db_session
):
    """Test members are ordered by creation date (newest first)"""
    # Create additional member
    new_member = User(
        email="newest@test.com",
        password_hash=hash_password("Newest1234"),
        first_name="Newest",
        last_name="Member",
        role=UserRole.MEMBER,
        is_email_verified=True
    )
    db_session.add(new_member)
    db_session.commit()
    
    response = client.get(
        "/api/admin/members",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify newest member is first
    assert data["members"][0]["email"] == "newest@test.com"


def test_list_members_non_admin_forbidden(client, member_headers):
    """Test non-administrator cannot list members
    
    Validates Requirement 7.2:
    - Administrative functions restricted to administrator role
    """
    response = client.get(
        "/api/admin/members",
        headers=member_headers
    )
    
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    error = data["detail"]["error"]
    assert error["code"] == "INSUFFICIENT_PERMISSIONS"


def test_list_members_unauthenticated(client):
    """Test unauthenticated user cannot list members"""
    response = client.get("/api/admin/members")
    
    # HTTPBearer returns 403 when no credentials provided
    assert response.status_code == 403


def test_list_members_includes_role_information(
    client, admin_headers, admin_user, member_user
):
    """Test member list includes role information
    
    Validates Requirement 7.3:
    - Display all members with their roles
    """
    response = client.get(
        "/api/admin/members",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    members_by_email = {m["email"]: m for m in data["members"]}
    
    assert members_by_email["admin@test.com"]["role"] == "administrator"
    assert members_by_email["member@test.com"]["role"] == "member"


# Tests for PUT /api/admin/members/:id/deactivate

def test_deactivate_member_success(client, admin_headers, member_user, db_session):
    """Test administrator can deactivate a member account
    
    Validates Requirement 7.4:
    - Administrator deactivates member account
    - Revokes access while preserving historical data
    """
    response = client.put(
        f"/api/admin/members/{member_user.id}/deactivate",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response
    assert data["id"] == str(member_user.id)
    assert data["email"] == member_user.email
    assert data["message"] == "Member account deactivated successfully"
    
    # Verify database update - access revoked
    db_session.refresh(member_user)
    assert member_user.is_email_verified is False
    # Handle timezone-aware comparison
    expires_at = member_user.membership_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert expires_at <= datetime.now(timezone.utc)


def test_deactivate_member_preserves_historical_data(
    client, admin_headers, member_user, db_session
):
    """Test deactivation preserves historical data
    
    Validates Requirement 7.4:
    - Preserves historical data (user record, relationships)
    """
    # Store original data
    original_email = member_user.email
    original_first_name = member_user.first_name
    original_last_name = member_user.last_name
    original_role = member_user.role
    original_id = member_user.id
    
    response = client.put(
        f"/api/admin/members/{member_user.id}/deactivate",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    
    # Verify user record still exists
    db_session.refresh(member_user)
    assert member_user.id == original_id
    assert member_user.email == original_email
    assert member_user.first_name == original_first_name
    assert member_user.last_name == original_last_name
    assert member_user.role == original_role
    
    # User record is preserved, only access is revoked


def test_deactivate_member_creates_audit_log(
    client, admin_headers, admin_user, member_user, db_session
):
    """Test deactivation creates audit log entry
    
    Validates Requirement 7.5:
    - Logs administrative action with admin identity
    """
    response = client.put(
        f"/api/admin/members/{member_user.id}/deactivate",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    
    # Verify audit log entry
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "deactivate_member",
        AuditLog.target_id == member_user.id
    ).first()
    
    assert audit_entry is not None
    assert audit_entry.admin_id == admin_user.id
    assert audit_entry.target_type == "user"
    assert audit_entry.details["member_email"] == member_user.email
    assert "old_is_email_verified" in audit_entry.details
    assert "new_is_email_verified" in audit_entry.details


def test_deactivate_member_prevents_login(
    client, admin_headers, member_user, db_session
):
    """Test deactivated member cannot login"""
    # Deactivate the member
    response = client.put(
        f"/api/admin/members/{member_user.id}/deactivate",
        headers=admin_headers
    )
    assert response.status_code == 200
    
    # Attempt to login
    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "member@test.com",
            "password": "Member1234"
        }
    )
    
    # Login should fail due to unverified email
    assert login_response.status_code == 401
    data = login_response.json()
    assert "detail" in data
    error = data["detail"]["error"]
    assert error["code"] == "EMAIL_NOT_VERIFIED"


def test_deactivate_member_non_admin_forbidden(client, member_headers, member_user):
    """Test non-administrator cannot deactivate members
    
    Validates Requirement 7.2:
    - Administrative functions restricted to administrator role
    """
    response = client.put(
        f"/api/admin/members/{member_user.id}/deactivate",
        headers=member_headers
    )
    
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    error = data["detail"]["error"]
    assert error["code"] == "INSUFFICIENT_PERMISSIONS"


def test_deactivate_member_unauthenticated(client, member_user):
    """Test unauthenticated user cannot deactivate members"""
    response = client.put(
        f"/api/admin/members/{member_user.id}/deactivate"
    )
    
    # HTTPBearer returns 403 when no credentials provided
    assert response.status_code == 403


def test_deactivate_member_not_found(client, admin_headers):
    """Test deactivating non-existent member returns 404"""
    from uuid import uuid4
    non_existent_id = uuid4()
    
    response = client.put(
        f"/api/admin/members/{non_existent_id}/deactivate",
        headers=admin_headers
    )
    
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    error = data["detail"]["error"]
    assert error["code"] == "MEMBER_NOT_FOUND"


def test_deactivate_already_deactivated_member(
    client, admin_headers, member_user, db_session
):
    """Test deactivating an already deactivated member"""
    # First deactivation
    response1 = client.put(
        f"/api/admin/members/{member_user.id}/deactivate",
        headers=admin_headers
    )
    assert response1.status_code == 200
    
    # Second deactivation (should still succeed)
    response2 = client.put(
        f"/api/admin/members/{member_user.id}/deactivate",
        headers=admin_headers
    )
    assert response2.status_code == 200
    
    # Verify both audit log entries exist
    audit_entries = db_session.query(AuditLog).filter(
        AuditLog.action == "deactivate_member",
        AuditLog.target_id == member_user.id
    ).all()
    
    assert len(audit_entries) == 2


def test_deactivate_member_updates_timestamp(
    client, admin_headers, member_user, db_session
):
    """Test deactivation updates the updated_at timestamp"""
    original_updated_at = member_user.updated_at
    
    response = client.put(
        f"/api/admin/members/{member_user.id}/deactivate",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    
    # Verify updated_at changed
    db_session.refresh(member_user)
    assert member_user.updated_at > original_updated_at

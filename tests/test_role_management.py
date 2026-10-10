"""Tests for role management endpoints
Feature: OPCP-website
Validates Requirements 7.1, 7.2, 7.5
"""
import pytest
from uuid import uuid4
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


def test_update_member_role_success(client, admin_headers, member_user, db_session):
    """Test administrator can successfully update a member's role
    
    Validates Requirements 7.1, 7.5:
    - Administrator assigns role to member
    - Action is logged in audit log
    """
    # Update member role to administrator
    response = client.put(
        f"/api/admin/members/{member_user.id}/role",
        json={"role": "administrator"},
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response
    assert data["id"] == str(member_user.id)
    assert data["email"] == member_user.email
    assert data["role"] == "administrator"
    assert data["message"] == "User role updated successfully"
    
    # Verify database update
    db_session.refresh(member_user)
    assert member_user.role == UserRole.ADMINISTRATOR
    
    # Verify audit log entry (Requirement 7.5)
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "update_member_role",
        AuditLog.target_id == member_user.id
    ).first()
    
    assert audit_entry is not None
    assert audit_entry.target_type == "user"
    assert audit_entry.details["old_role"] == "member"
    assert audit_entry.details["new_role"] == "administrator"
    assert audit_entry.details["member_email"] == member_user.email


def test_update_member_role_to_visitor(client, admin_headers, member_user, db_session):
    """Test administrator can downgrade a member to visitor role"""
    response = client.put(
        f"/api/admin/members/{member_user.id}/role",
        json={"role": "visitor"},
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "visitor"
    
    # Verify database update
    db_session.refresh(member_user)
    assert member_user.role == UserRole.VISITOR


def test_update_member_role_non_admin_forbidden(client, member_headers, member_user):
    """Test non-administrator cannot update roles
    
    Validates Requirement 7.2:
    - Administrative functions restricted to administrator role
    """
    # Create another member to try to update
    response = client.put(
        f"/api/admin/members/{member_user.id}/role",
        json={"role": "administrator"},
        headers=member_headers
    )
    
    assert response.status_code == 403
    data = response.json()
    # FastAPI wraps HTTPException detail in a "detail" field
    assert "detail" in data
    error = data["detail"]["error"]
    assert error["code"] == "INSUFFICIENT_PERMISSIONS"
    assert "administrator" in error["message"].lower()


def test_update_member_role_unauthenticated(client, member_user):
    """Test unauthenticated user cannot update roles"""
    response = client.put(
        f"/api/admin/members/{member_user.id}/role",
        json={"role": "administrator"}
    )
    
    # HTTPBearer returns 403 when no credentials provided
    assert response.status_code == 403


def test_update_member_role_invalid_role(client, admin_headers, member_user):
    """Test updating with invalid role value returns error"""
    response = client.put(
        f"/api/admin/members/{member_user.id}/role",
        json={"role": "superadmin"},
        headers=admin_headers
    )
    
    # Pydantic validation returns 422 for invalid enum values
    assert response.status_code == 422
    data = response.json()
    # Pydantic validation errors have a different format
    assert "detail" in data


def test_update_member_role_member_not_found(client, admin_headers):
    """Test updating non-existent member returns 404"""
    non_existent_id = uuid4()
    response = client.put(
        f"/api/admin/members/{non_existent_id}/role",
        json={"role": "administrator"},
        headers=admin_headers
    )
    
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    error = data["detail"]["error"]
    assert error["code"] == "MEMBER_NOT_FOUND"


def test_update_member_role_audit_log_includes_admin_id(
    client, admin_headers, admin_user, member_user, db_session
):
    """Test audit log includes administrator ID
    
    Validates Requirement 7.5:
    - Audit log maintains administrator identity
    """
    response = client.put(
        f"/api/admin/members/{member_user.id}/role",
        json={"role": "administrator"},
        headers=admin_headers
    )
    
    assert response.status_code == 200
    
    # Verify audit log has admin_id
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "update_member_role",
        AuditLog.target_id == member_user.id
    ).first()
    
    assert audit_entry.admin_id == admin_user.id


def test_update_member_role_multiple_times(client, admin_headers, member_user, db_session):
    """Test updating the same member's role multiple times"""
    # First update: member -> administrator
    response1 = client.put(
        f"/api/admin/members/{member_user.id}/role",
        json={"role": "administrator"},
        headers=admin_headers
    )
    assert response1.status_code == 200
    
    # Second update: administrator -> visitor
    response2 = client.put(
        f"/api/admin/members/{member_user.id}/role",
        json={"role": "visitor"},
        headers=admin_headers
    )
    assert response2.status_code == 200
    
    # Verify final state
    db_session.refresh(member_user)
    assert member_user.role == UserRole.VISITOR
    
    # Verify both audit log entries exist
    audit_entries = db_session.query(AuditLog).filter(
        AuditLog.action == "update_member_role",
        AuditLog.target_id == member_user.id
    ).all()
    
    assert len(audit_entries) == 2


def test_update_member_role_preserves_other_fields(
    client, admin_headers, member_user, db_session
):
    """Test that updating role doesn't affect other user fields"""
    original_email = member_user.email
    original_first_name = member_user.first_name
    original_last_name = member_user.last_name
    original_created_at = member_user.created_at
    
    response = client.put(
        f"/api/admin/members/{member_user.id}/role",
        json={"role": "administrator"},
        headers=admin_headers
    )
    
    assert response.status_code == 200
    
    # Verify other fields unchanged
    db_session.refresh(member_user)
    assert member_user.email == original_email
    assert member_user.first_name == original_first_name
    assert member_user.last_name == original_last_name
    assert member_user.created_at == original_created_at
    # updated_at should change
    assert member_user.updated_at > original_created_at

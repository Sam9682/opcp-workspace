"""Tests for audit log endpoint
Feature: OPCP-website
Validates Requirements 7.5
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
def sample_audit_entries(db_session, admin_user, member_user):
    """Create sample audit log entries for testing"""
    now = datetime.now(timezone.utc)
    
    entries = [
        AuditLog(
            admin_id=admin_user.id,
            action="update_member_role",
            target_type="user",
            target_id=member_user.id,
            details={"old_role": "member", "new_role": "administrator"},
            timestamp=now - timedelta(days=5)
        ),
        AuditLog(
            admin_id=admin_user.id,
            action="deactivate_member",
            target_type="user",
            target_id=member_user.id,
            details={"member_email": "member@test.com"},
            timestamp=now - timedelta(days=3)
        ),
        AuditLog(
            admin_id=admin_user.id,
            action="update_member_role",
            target_type="user",
            target_id=member_user.id,
            details={"old_role": "administrator", "new_role": "visitor"},
            timestamp=now - timedelta(days=1)
        ),
    ]
    
    for entry in entries:
        db_session.add(entry)
    
    db_session.commit()
    return entries


def test_get_audit_log_success(client, admin_headers, sample_audit_entries):
    """Test administrator can retrieve audit log
    
    Validates Requirement 7.5:
    - Administrator can view audit log of all administrative actions
    """
    response = client.get(
        "/api/admin/audit-log",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "entries" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    
    # Verify entries (should have at least the 3 sample entries, plus login audit entry)
    assert data["total"] >= 3
    assert len(data["entries"]) >= 3
    assert data["page"] == 1
    assert data["page_size"] == 50
    
    # Verify entries are ordered by timestamp (most recent first)
    timestamps = [entry["timestamp"] for entry in data["entries"]]
    assert timestamps == sorted(timestamps, reverse=True)
    
    # Verify entry structure
    first_entry = data["entries"][0]
    assert "id" in first_entry
    assert "admin_id" in first_entry
    assert "admin_email" in first_entry
    assert "action" in first_entry
    assert "target_type" in first_entry
    assert "target_id" in first_entry
    assert "details" in first_entry
    assert "timestamp" in first_entry
    
    # Verify admin email is denormalized (for entries with admin_id)
    if first_entry["admin_id"]:
        assert first_entry["admin_email"] == "admin@test.com"


def test_get_audit_log_filter_by_admin(client, admin_headers, admin_user, sample_audit_entries):
    """Test filtering audit log by admin ID
    
    Validates Requirement 7.5:
    - Support filtering by admin
    """
    response = client.get(
        f"/api/admin/audit-log?admin_id={admin_user.id}",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # All entries should be from the specified admin (at least the 3 sample entries)
    assert data["total"] >= 3
    for entry in data["entries"]:
        assert entry["admin_id"] == str(admin_user.id)


def test_get_audit_log_filter_by_action(client, admin_headers, sample_audit_entries):
    """Test filtering audit log by action type
    
    Validates Requirement 7.5:
    - Support filtering by action type
    """
    response = client.get(
        "/api/admin/audit-log?action=update_member_role",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should only return entries with the specified action
    assert data["total"] == 2
    for entry in data["entries"]:
        assert entry["action"] == "update_member_role"


def test_get_audit_log_filter_by_date_range(client, admin_headers, sample_audit_entries):
    """Test filtering audit log by date range
    
    Validates Requirement 7.5:
    - Support filtering by date range
    """
    now = datetime.now(timezone.utc)
    # Use simpler date format without microseconds
    start_date = (now - timedelta(days=4)).strftime("%Y-%m-%dT%H:%M:%S")
    end_date = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
    
    response = client.get(
        f"/api/admin/audit-log?start_date={start_date}&end_date={end_date}",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should only return entries within the date range
    assert data["total"] == 1
    assert data["entries"][0]["action"] == "deactivate_member"


def test_get_audit_log_pagination(client, admin_headers, db_session, admin_user, member_user):
    """Test audit log pagination
    
    Validates Requirement 7.5:
    - Paginate results
    """
    # Create 10 audit entries
    now = datetime.now(timezone.utc)
    for i in range(10):
        entry = AuditLog(
            admin_id=admin_user.id,
            action=f"test_action_{i}",
            target_type="user",
            target_id=member_user.id,
            details={"index": i},
            timestamp=now - timedelta(minutes=i)
        )
        db_session.add(entry)
    db_session.commit()
    
    # Get first page with page_size=5
    response1 = client.get(
        "/api/admin/audit-log?page=1&page_size=5",
        headers=admin_headers
    )
    
    assert response1.status_code == 200
    data1 = response1.json()
    # Should have at least 10 entries (plus login audit entry)
    assert data1["total"] >= 10
    assert len(data1["entries"]) == 5
    assert data1["page"] == 1
    assert data1["page_size"] == 5
    
    # Get second page
    response2 = client.get(
        "/api/admin/audit-log?page=2&page_size=5",
        headers=admin_headers
    )
    
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["total"] >= 10
    assert len(data2["entries"]) == 5
    assert data2["page"] == 2
    
    # Verify no overlap between pages
    page1_ids = {entry["id"] for entry in data1["entries"]}
    page2_ids = {entry["id"] for entry in data2["entries"]}
    assert len(page1_ids.intersection(page2_ids)) == 0


def test_get_audit_log_empty_result(client, admin_headers, db_session):
    """Test audit log with no matching entries"""
    response = client.get(
        "/api/admin/audit-log?action=nonexistent_action",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["entries"]) == 0


def test_get_audit_log_non_admin_forbidden(client, member_headers):
    """Test non-administrator cannot access audit log
    
    Validates Requirement 7.2:
    - Administrative functions restricted to administrator role
    """
    response = client.get(
        "/api/admin/audit-log",
        headers=member_headers
    )
    
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    error = data["detail"]["error"]
    assert error["code"] == "INSUFFICIENT_PERMISSIONS"


def test_get_audit_log_unauthenticated(client):
    """Test unauthenticated user cannot access audit log"""
    response = client.get("/api/admin/audit-log")
    
    # HTTPBearer returns 403 when no credentials provided
    assert response.status_code == 403


def test_get_audit_log_combined_filters(client, admin_headers, admin_user, sample_audit_entries):
    """Test combining multiple filters"""
    now = datetime.now(timezone.utc)
    # Use simpler date format
    start_date = (now - timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%S")
    end_date = now.strftime("%Y-%m-%dT%H:%M:%S")
    
    response = client.get(
        f"/api/admin/audit-log?admin_id={admin_user.id}&action=update_member_role&start_date={start_date}&end_date={end_date}",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should return only entries matching all filters
    assert data["total"] == 2
    for entry in data["entries"]:
        assert entry["admin_id"] == str(admin_user.id)
        assert entry["action"] == "update_member_role"


def test_get_audit_log_max_page_size(client, admin_headers, db_session, admin_user, member_user):
    """Test page_size is capped at 100"""
    # Create 150 audit entries
    now = datetime.now(timezone.utc)
    for i in range(150):
        entry = AuditLog(
            admin_id=admin_user.id,
            action=f"test_action_{i}",
            target_type="user",
            target_id=member_user.id,
            details={"index": i},
            timestamp=now - timedelta(minutes=i)
        )
        db_session.add(entry)
    db_session.commit()
    
    # Request with page_size > 100
    response = client.get(
        "/api/admin/audit-log?page=1&page_size=200",
        headers=admin_headers
    )
    
    assert response.status_code == 422  # Validation error for exceeding max


def test_get_audit_log_invalid_page(client, admin_headers):
    """Test invalid page number returns validation error"""
    response = client.get(
        "/api/admin/audit-log?page=0",
        headers=admin_headers
    )
    
    assert response.status_code == 422  # Validation error


def test_get_audit_log_includes_details(client, admin_headers, sample_audit_entries):
    """Test audit log entries include details field"""
    response = client.get(
        "/api/admin/audit-log",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Find the role update entry
    role_update_entry = next(
        (e for e in data["entries"] if e["action"] == "update_member_role"),
        None
    )
    
    assert role_update_entry is not None
    assert role_update_entry["details"] is not None
    assert "old_role" in role_update_entry["details"]
    assert "new_role" in role_update_entry["details"]

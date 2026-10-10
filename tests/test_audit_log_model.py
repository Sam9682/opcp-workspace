"""Tests for AuditLog model"""
import pytest
from datetime import datetime
from app.models import AuditLog, User, UserRole


def test_create_audit_log(db_session):
    """Test creating an audit log entry"""
    # Create an admin user first
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
    
    # Create an audit log entry
    audit_log = AuditLog(
        admin_id=admin.id,
        action="user_role_changed",
        target_type="user",
        target_id=admin.id,
        details={"old_role": "member", "new_role": "administrator"}
    )
    db_session.add(audit_log)
    db_session.commit()
    
    # Verify audit log was created
    assert audit_log.id is not None
    assert audit_log.admin_id == admin.id
    assert audit_log.action == "user_role_changed"
    assert audit_log.target_type == "user"
    assert audit_log.target_id == admin.id
    assert audit_log.details == {"old_role": "member", "new_role": "administrator"}
    assert audit_log.timestamp is not None
    assert isinstance(audit_log.timestamp, datetime)


def test_audit_log_optional_fields(db_session):
    """Test that target_type, target_id, and details are optional"""
    admin = User(
        email="admin2@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create audit log with minimal fields
    audit_log = AuditLog(
        admin_id=admin.id,
        action="system_backup"
    )
    db_session.add(audit_log)
    db_session.commit()
    
    assert audit_log.target_type is None
    assert audit_log.target_id is None
    assert audit_log.details is None


def test_audit_log_admin_relationship(db_session):
    """Test relationship between AuditLog and admin User"""
    admin = User(
        email="admin3@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    audit_log = AuditLog(
        admin_id=admin.id,
        action="test_action"
    )
    db_session.add(audit_log)
    db_session.commit()
    
    # Test relationship from audit log to admin
    assert audit_log.admin == admin
    
    # Test relationship from admin to audit logs
    assert len(admin.audit_logs) == 1
    assert admin.audit_logs[0] == audit_log


def test_audit_log_admin_index(db_session):
    """Test that index on admin_id exists and works efficiently"""
    admin = User(
        email="admin4@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create multiple audit log entries
    for i in range(5):
        audit_log = AuditLog(
            admin_id=admin.id,
            action=f"action_{i}"
        )
        db_session.add(audit_log)
    db_session.commit()
    
    # Query by admin_id (should use idx_audit_admin)
    logs = db_session.query(AuditLog).filter(
        AuditLog.admin_id == admin.id
    ).all()
    assert len(logs) == 5


def test_audit_log_timestamp_index(db_session):
    """Test that index on timestamp exists and works efficiently"""
    admin = User(
        email="admin5@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create multiple audit log entries
    for i in range(5):
        audit_log = AuditLog(
            admin_id=admin.id,
            action=f"action_{i}"
        )
        db_session.add(audit_log)
    db_session.commit()
    
    # Query by timestamp (should use idx_audit_timestamp)
    from datetime import timezone, timedelta
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    logs = db_session.query(AuditLog).filter(
        AuditLog.timestamp >= recent_time
    ).all()
    assert len(logs) == 5


def test_audit_log_jsonb_details(db_session):
    """Test storing complex JSON data in details field"""
    admin = User(
        email="admin6@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create audit log with complex details
    complex_details = {
        "action_type": "bulk_update",
        "affected_users": [
            {"id": "123", "email": "user1@example.com"},
            {"id": "456", "email": "user2@example.com"}
        ],
        "changes": {
            "role": "member",
            "status": "active"
        },
        "metadata": {
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0"
        }
    }
    
    audit_log = AuditLog(
        admin_id=admin.id,
        action="bulk_user_update",
        details=complex_details
    )
    db_session.add(audit_log)
    db_session.commit()
    
    # Verify complex details are stored correctly
    assert audit_log.details == complex_details
    assert audit_log.details["action_type"] == "bulk_update"
    assert len(audit_log.details["affected_users"]) == 2
    assert audit_log.details["changes"]["role"] == "member"


def test_audit_log_different_target_types(db_session):
    """Test audit log with different target types"""
    admin = User(
        email="admin7@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Test different target types
    target_types = ["user", "document", "event", "forum_post", "payment"]
    
    for target_type in target_types:
        audit_log = AuditLog(
            admin_id=admin.id,
            action=f"delete_{target_type}",
            target_type=target_type
        )
        db_session.add(audit_log)
    db_session.commit()
    
    # Verify all were created
    logs = db_session.query(AuditLog).filter(
        AuditLog.admin_id == admin.id
    ).all()
    assert len(logs) == 5


def test_audit_log_repr(db_session):
    """Test AuditLog __repr__ method"""
    admin = User(
        email="admin8@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    audit_log = AuditLog(
        admin_id=admin.id,
        action="test_action"
    )
    db_session.add(audit_log)
    db_session.commit()
    
    repr_str = repr(audit_log)
    assert "AuditLog" in repr_str
    assert str(audit_log.id) in repr_str
    assert str(admin.id) in repr_str
    assert "test_action" in repr_str


def test_audit_log_cascade_delete(db_session):
    """Test that deleting an admin user cascades to audit logs"""
    admin = User(
        email="admin9@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    audit_log = AuditLog(
        admin_id=admin.id,
        action="test_action"
    )
    db_session.add(audit_log)
    db_session.commit()
    
    audit_log_id = audit_log.id
    
    # Delete admin
    db_session.delete(admin)
    db_session.commit()
    
    # Verify audit log was also deleted
    deleted_log = db_session.query(AuditLog).filter(
        AuditLog.id == audit_log_id
    ).first()
    assert deleted_log is None


def test_audit_log_multiple_actions_per_admin(db_session):
    """Test that an admin can have multiple audit log entries"""
    admin = User(
        email="admin10@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create multiple audit log entries for the same admin
    actions = [
        "user_created",
        "user_role_changed",
        "document_deleted",
        "event_cancelled",
        "post_hidden"
    ]
    
    for action in actions:
        audit_log = AuditLog(
            admin_id=admin.id,
            action=action
        )
        db_session.add(audit_log)
    db_session.commit()
    
    # Verify all logs were created
    logs = db_session.query(AuditLog).filter(
        AuditLog.admin_id == admin.id
    ).all()
    assert len(logs) == 5
    
    # Verify actions are correct
    log_actions = [log.action for log in logs]
    assert set(log_actions) == set(actions)


def test_audit_log_query_by_action(db_session):
    """Test querying audit logs by action type"""
    admin = User(
        email="admin11@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMINISTRATOR,
        is_email_verified=True
    )
    db_session.add(admin)
    db_session.commit()
    
    # Create audit logs with different actions
    for i in range(3):
        audit_log = AuditLog(
            admin_id=admin.id,
            action="user_role_changed"
        )
        db_session.add(audit_log)
    
    for i in range(2):
        audit_log = AuditLog(
            admin_id=admin.id,
            action="document_deleted"
        )
        db_session.add(audit_log)
    db_session.commit()
    
    # Query by specific action
    role_change_logs = db_session.query(AuditLog).filter(
        AuditLog.action == "user_role_changed"
    ).all()
    assert len(role_change_logs) == 3
    
    delete_logs = db_session.query(AuditLog).filter(
        AuditLog.action == "document_deleted"
    ).all()
    assert len(delete_logs) == 2

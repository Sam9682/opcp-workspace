"""Tests for User model"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError
from app.models import User, UserRole


def test_create_user(db_session):
    """Test creating a user with all required fields"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        first_name="John",
        last_name="Doe",
        role=UserRole.MEMBER,
        is_email_verified=False
    )
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.password_hash == "hashed_password"
    assert user.first_name == "John"
    assert user.last_name == "Doe"
    assert user.role == UserRole.MEMBER
    assert user.is_email_verified is False
    assert user.membership_expires_at is None
    assert user.created_at is not None
    assert user.updated_at is not None


def test_user_role_enum():
    """Test UserRole enum values"""
    assert UserRole.VISITOR.value == "visitor"
    assert UserRole.MEMBER.value == "member"
    assert UserRole.ADMINISTRATOR.value == "administrator"


def test_user_with_membership_expiration(db_session):
    """Test creating a user with membership expiration date"""
    expiration_date = datetime.now(timezone.utc) + timedelta(days=365)
    
    user = User(
        email="member@example.com",
        password_hash="hashed_password",
        first_name="Jane",
        last_name="Smith",
        role=UserRole.MEMBER,
        is_email_verified=True,
        membership_expires_at=expiration_date
    )
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    assert user.membership_expires_at is not None
    assert user.is_email_verified is True


def test_user_email_unique_constraint(db_session):
    """Test that email must be unique"""
    user1 = User(
        email="duplicate@example.com",
        password_hash="hashed_password",
        first_name="User",
        last_name="One",
        role=UserRole.MEMBER,
        is_email_verified=False
    )
    
    db_session.add(user1)
    db_session.commit()
    
    # Try to create another user with the same email
    user2 = User(
        email="duplicate@example.com",
        password_hash="different_hash",
        first_name="User",
        last_name="Two",
        role=UserRole.MEMBER,
        is_email_verified=False
    )
    
    db_session.add(user2)
    
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_administrator_role(db_session):
    """Test creating a user with administrator role"""
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
    db_session.refresh(admin)
    
    assert admin.role == UserRole.ADMINISTRATOR


def test_user_repr(db_session):
    """Test User __repr__ method"""
    user = User(
        email="repr@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=False
    )
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    repr_str = repr(user)
    assert "User" in repr_str
    assert str(user.id) in repr_str
    assert "repr@example.com" in repr_str
    assert "MEMBER" in repr_str

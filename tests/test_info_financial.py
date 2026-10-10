"""Tests for financial transparency endpoint"""
import pytest
from sqlalchemy.orm import Session
from app.models import User, UserRole
from app.auth.password import hash_password
from app.auth.token import create_access_token
from datetime import datetime, timezone


def test_get_financial_reports_success(client, test_user):
    """Test successful retrieval of financial reports.
    
    Validates Requirements 8.5:
    - Returns list of financial reports
    - Accessible to authenticated members
    """
    # Create auth headers
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value
        }
    )
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/info/financial-reports", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify reports list
    assert "reports" in data
    assert isinstance(data["reports"], list)
    assert len(data["reports"]) > 0
    
    # Verify message
    assert "message" in data
    
    # Verify report structure
    report = data["reports"][0]
    assert "id" in report
    assert "title" in report
    assert "year" in report
    assert "description" in report
    assert "published_date" in report


def test_financial_reports_requires_authentication(client):
    """Test that financial reports require authentication.
    
    Validates Requirements 8.5:
    - Financial reports are only accessible to members
    """
    # No authentication header provided
    response = client.get("/api/info/financial-reports")
    
    # Should fail with 403 Forbidden (FastAPI returns 403 when no credentials provided)
    assert response.status_code == 403


def test_financial_reports_invalid_token(client):
    """Test that invalid token is rejected."""
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/api/info/financial-reports", headers=headers)
    
    # Should fail with 401 Unauthorized
    assert response.status_code == 401


def test_financial_reports_contains_multiple_years(client, test_user):
    """Test that financial reports include multiple years."""
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value
        }
    )
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/info/financial-reports", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    reports = data["reports"]
    years = [report["year"] for report in reports]
    
    # Should have reports for multiple years
    assert len(set(years)) > 1, "Should have reports for multiple years"


def test_financial_reports_sorted_by_year(client, test_user):
    """Test that financial reports are sorted by year (newest first)."""
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value
        }
    )
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/info/financial-reports", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    reports = data["reports"]
    years = [report["year"] for report in reports]
    
    # Should be sorted in descending order (newest first)
    assert years == sorted(years, reverse=True), "Reports should be sorted by year (newest first)"


def test_financial_reports_have_descriptions(client, test_user):
    """Test that all financial reports have descriptions."""
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value
        }
    )
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/info/financial-reports", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    reports = data["reports"]
    
    # All reports should have non-empty descriptions
    for report in reports:
        assert "description" in report
        assert len(report["description"]) > 0


def test_financial_reports_transparency_message(client, test_user):
    """Test that response includes transparency message."""
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "email": test_user.email,
            "role": test_user.role.value
        }
    )
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/info/financial-reports", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should include a message about transparency
    assert "message" in data
    assert "transparency" in data["message"].lower() or "transparent" in data["message"].lower()


def test_financial_reports_with_expired_membership(client, db_session: Session):
    """Test that users with expired membership can still access financial reports.
    
    Financial transparency should be available to all members regardless of payment status.
    """
    # Create user with expired membership
    expired_user = User(
        email="expired@example.com",
        password_hash=hash_password("Test1234"),
        first_name="Expired",
        last_name="User",
        role=UserRole.MEMBER,
        is_email_verified=True,
        membership_expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc)
    )
    db_session.add(expired_user)
    db_session.commit()
    db_session.refresh(expired_user)
    
    # Create token for expired user
    token = create_access_token(
        data={
            "sub": str(expired_user.id),
            "email": expired_user.email,
            "role": expired_user.role.value
        }
    )
    headers = {"Authorization": f"Bearer {token}"}
    
    # Should still be able to access financial reports
    response = client.get("/api/info/financial-reports", headers=headers)
    assert response.status_code == 200

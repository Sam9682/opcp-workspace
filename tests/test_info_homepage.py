"""Tests for homepage information endpoint"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_homepage_info_success():
    """Test successful retrieval of homepage information.
    
    Validates Requirements 1.1, 1.2, 1.4, 8.1, 8.2:
    - Returns PSMC information
    - Returns mission and activities
    - Returns contact information
    """
    response = client.get("/api/info/homepage")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify PSMC information
    assert "PSMC" in data
    assert data["PSMC"]["name"] == "OPCP"
    assert "address" in data["PSMC"]
    assert "board_members" in data["PSMC"]
    assert len(data["PSMC"]["board_members"]) > 0
    
    # Verify board member structure
    board_member = data["PSMC"]["board_members"][0]
    assert "name" in board_member
    assert "position" in board_member
    
    # Verify mission and activities
    assert "mission" in data
    assert len(data["mission"]) > 0
    assert "activities" in data
    assert len(data["activities"]) > 0
    
    # Verify contact information
    assert "contact_email" in data
    assert "@" in data["contact_email"]


def test_homepage_info_contains_president():
    """Test that homepage includes president information."""
    response = client.get("/api/info/homepage")
    
    assert response.status_code == 200
    data = response.json()
    
    board_members = data["PSMC"]["board_members"]
    positions = [member["position"] for member in board_members]
    
    # Should have a president
    assert any("Président" in pos for pos in positions)


def test_homepage_info_contains_treasurer():
    """Test that homepage includes treasurer information."""
    response = client.get("/api/info/homepage")
    
    assert response.status_code == 200
    data = response.json()
    
    board_members = data["PSMC"]["board_members"]
    positions = [member["position"] for member in board_members]
    
    # Should have a treasurer (masculine or feminine form)
    assert any("Trésorier" in pos or "Trésorière" in pos for pos in positions)


def test_homepage_info_contains_secretary():
    """Test that homepage includes secretary information."""
    response = client.get("/api/info/homepage")
    
    assert response.status_code == 200
    data = response.json()
    
    board_members = data["PSMC"]["board_members"]
    positions = [member["position"] for member in board_members]
    
    # Should have a secretary
    assert any("Secrétaire" in pos for pos in positions)


def test_homepage_info_public_access():
    """Test that homepage information is accessible without authentication."""
    # No authentication header provided
    response = client.get("/api/info/homepage")
    
    # Should still succeed (public endpoint)
    assert response.status_code == 200


def test_homepage_info_response_structure():
    """Test that homepage response has correct structure."""
    response = client.get("/api/info/homepage")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify all required fields are present
    required_fields = ["PSMC", "mission", "activities", "contact_email"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # Verify PSMC structure
    PSMC_fields = ["name", "address", "board_members"]
    for field in PSMC_fields:
        assert field in data["PSMC"], f"Missing PSMC field: {field}"

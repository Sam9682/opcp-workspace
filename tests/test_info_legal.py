"""Tests for legal information endpoints"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_legal_info_success():
    """Test successful retrieval of legal information.
    
    Validates Requirements 8.2, 8.3:
    - Returns PSMC statutes
    - Returns internal regulations
    """
    response = client.get("/api/info/legal")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify statutes
    assert "statutes" in data
    assert "title" in data["statutes"]
    assert "description" in data["statutes"]
    assert "content" in data["statutes"]
    assert len(data["statutes"]["content"]) > 0
    
    # Verify regulations
    assert "regulations" in data
    assert "title" in data["regulations"]
    assert "description" in data["regulations"]
    assert "content" in data["regulations"]
    assert len(data["regulations"]["content"]) > 0


def test_legal_info_public_access():
    """Test that legal information is accessible without authentication.
    
    Legal documents must be publicly accessible for transparency.
    """
    # No authentication header provided
    response = client.get("/api/info/legal")
    
    # Should still succeed (public endpoint)
    assert response.status_code == 200


def test_legal_info_statutes_content():
    """Test that statutes contain expected legal content."""
    response = client.get("/api/info/legal")
    
    assert response.status_code == 200
    data = response.json()
    
    statutes_content = data["statutes"]["content"]
    
    # Verify key sections are present
    assert "Article" in statutes_content
    assert "PSMC" in statutes_content.lower()


def test_legal_info_regulations_content():
    """Test that regulations contain expected content."""
    response = client.get("/api/info/legal")
    
    assert response.status_code == 200
    data = response.json()
    
    regulations_content = data["regulations"]["content"]
    
    # Verify key sections are present
    assert "Article" in regulations_content
    assert "règlement" in regulations_content.lower() or "reglement" in regulations_content.lower()


def test_get_board_info_success():
    """Test successful retrieval of board information.
    
    Validates Requirements 8.2:
    - Returns board member information
    """
    response = client.get("/api/info/board")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify board members
    assert "board_members" in data
    assert len(data["board_members"]) > 0
    
    # Verify last updated date
    assert "last_updated" in data
    
    # Verify board member structure
    board_member = data["board_members"][0]
    assert "name" in board_member
    assert "position" in board_member


def test_board_info_public_access():
    """Test that board information is accessible without authentication."""
    # No authentication header provided
    response = client.get("/api/info/board")
    
    # Should still succeed (public endpoint)
    assert response.status_code == 200


def test_board_info_contains_all_positions():
    """Test that board information includes all required positions."""
    response = client.get("/api/info/board")
    
    assert response.status_code == 200
    data = response.json()
    
    positions = [member["position"] for member in data["board_members"]]
    
    # Should have president, treasurer, and secretary (masculine or feminine forms)
    assert any("Président" in pos for pos in positions)
    assert any("Trésorier" in pos or "Trésorière" in pos for pos in positions)
    assert any("Secrétaire" in pos for pos in positions)


def test_board_info_has_contact_details():
    """Test that board members have contact information."""
    response = client.get("/api/info/board")
    
    assert response.status_code == 200
    data = response.json()
    
    # At least one board member should have an email
    has_email = any("email" in member and member["email"] for member in data["board_members"])
    assert has_email, "Board members should have contact email addresses"

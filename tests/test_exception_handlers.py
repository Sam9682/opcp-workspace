"""Tests for global exception handlers.

This module tests the custom exception handlers to ensure consistent error responses.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.exceptions import (
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    ServerError
)


client = TestClient(app)


def test_validation_error_response_format():
    """Test that validation errors return consistent format."""
    # Try to register with invalid data (missing required fields)
    response = client.post("/api/auth/register", json={})
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    
    # Check error response structure
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    assert "details" in data["error"]
    assert "timestamp" in data["error"]
    assert "requestId" in data["error"]
    
    # Check error code
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_authentication_error_response():
    """Test that authentication errors return 401 with correct format."""
    # Try to login with invalid credentials
    response = client.post("/api/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "WrongPassword123"
    })
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    
    # Check error response structure (should be unwrapped by handler)
    assert "error" in data
    assert data["error"]["code"] in ["INVALID_CREDENTIALS", "AUTHENTICATION_ERROR"]


def test_error_response_has_request_id():
    """Test that all error responses include a request ID for tracking."""
    response = client.post("/api/auth/register", json={})
    
    data = response.json()
    assert "error" in data
    assert "requestId" in data["error"]
    assert len(data["error"]["requestId"]) > 0


def test_error_response_has_timestamp():
    """Test that all error responses include a timestamp."""
    response = client.post("/api/auth/register", json={})
    
    data = response.json()
    assert "error" in data
    assert "timestamp" in data["error"]
    # Check it's in ISO format
    assert "T" in data["error"]["timestamp"]
    assert "Z" in data["error"]["timestamp"] or "+" in data["error"]["timestamp"]


def test_error_response_consistent_format():
    """Test that all errors follow the consistent format."""
    # Test validation error
    response = client.post("/api/auth/register", json={})
    data = response.json()
    
    # Check structure
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    assert "details" in data["error"]
    assert "timestamp" in data["error"]
    assert "requestId" in data["error"]

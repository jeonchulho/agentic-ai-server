"""
Test API endpoints.
"""
import pytest
from fastapi import status


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "status" in data


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "version" in data


def test_summarize_text_missing_field(client):
    """Test summarize endpoint with missing field."""
    response = client.post(
        "/api/v1/summarize/text",
        json={}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_translate_missing_fields(client):
    """Test translate endpoint with missing fields."""
    response = client.post(
        "/api/v1/translate",
        json={"text": "Hello"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_legacy_summary_invalid_type(client):
    """Test legacy summary with invalid data type."""
    response = client.get("/api/v1/legacy/summary/invalid_type")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

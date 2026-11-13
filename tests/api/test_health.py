"""Tests for Health and Root endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient) -> None:
    """Verify root endpoint returns service info and documentation links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["service"] == "Bookabook PDF Engine API"
    assert "version" in data
    assert data["docs_url"] == "/docs"
    assert data["health_url"] == "/api/health"


def test_health_check_healthy(client: TestClient) -> None:
    """Verify /api/health reports healthy status and SQLite connectivity."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database_connected"] is True
    assert data["app_name"] == "Bookabook PDF Engine API"
    assert "version" in data
    assert "timestamp" in data


def test_health_check_no_sensitive_info_leaked(client: TestClient) -> None:
    """Ensure /api/health never leaks absolute system paths or internal credentials."""
    response = client.get("/api/health")
    data = response.json()
    content_str = str(data)
    assert "C:\\" not in content_str
    assert "/data" not in content_str
    assert "password" not in content_str.lower()
    assert "secret" not in content_str.lower()


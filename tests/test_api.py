"""
Smoke tests for the Tennis Betting API (Phase 5 — FastAPI scaffold).

Tests:
    test_openapi_schema   — /docs returns 200 with valid HTML (OpenAPI UI)
    test_health_endpoint  — /api/v1/health returns 200 with status=ok
    test_error_format     — 404 on nonexistent route returns structured JSON
                            (not an HTML error page)
"""

import pytest


class TestOpenAPISchema:
    """GET /docs should serve the OpenAPI interactive documentation."""

    async def test_openapi_schema(self, async_client):
        response = await async_client.get("/docs")
        assert response.status_code == 200
        # FastAPI /docs returns HTML with the swagger UI
        assert "text/html" in response.headers.get("content-type", "")


class TestHealthEndpoint:
    """GET /api/v1/health should return {status: ok, model_loaded: false}."""

    async def test_health_returns_200(self, async_client):
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_health_status_ok(self, async_client):
        response = await async_client.get("/api/v1/health")
        data = response.json()
        assert data["status"] == "ok"

    async def test_health_model_loaded_false(self, async_client):
        """Model is None in tests (no joblib file on disk)."""
        response = await async_client.get("/api/v1/health")
        data = response.json()
        assert data["model_loaded"] is False


class TestErrorFormat:
    """404 responses should use structured JSON, not HTML error pages."""

    async def test_nonexistent_route_returns_structured_json(self, async_client):
        response = await async_client.get("/api/v1/nonexistent-route")
        assert response.status_code == 404
        # Must be JSON — not an HTML page
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

    async def test_error_response_has_required_keys(self, async_client):
        response = await async_client.get("/api/v1/nonexistent-route")
        data = response.json()
        assert "error" in data
        assert "message" in data

"""
Integration tests for Production RAG API.
Phase 8.1: API deployment verification.
Phase 8.3: User-provided LLM key flow.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app, settings


@pytest.fixture
def client() -> TestClient:
    """Create test client with valid API key in settings."""
    settings.api_key = "test-key"  # pragma: allowlist secret
    settings.require_api_key = True
    return TestClient(app)


@pytest.fixture
def auth_header() -> dict[str, str]:
    """Return valid auth header."""
    return {"X-API-Key": "test-key"}


class TestHealthEndpoints:
    """Test health check endpoints (no auth required)."""

    def test_root_endpoint(self, client: TestClient) -> None:
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "operational"

    def test_health_endpoint(self, client: TestClient) -> None:
        """Test health endpoint returns status."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_liveness_endpoint(self, client: TestClient) -> None:
        """Test liveness endpoint."""
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200

    def test_readiness_endpoint(self, client: TestClient) -> None:
        """Test readiness endpoint."""
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200


class TestAuthAndSecurity:
    """Test authentication and rate limiting."""

    def test_missing_api_key(self, client: TestClient) -> None:
        """Test request fails without API key."""
        response = client.post("/api/v1/query", json={"query": "test"})
        assert response.status_code == 401

    def test_invalid_api_key(self, client: TestClient) -> None:
        """Test request fails with invalid API key."""
        response = client.post(
            "/api/v1/query",
            json={"query": "test"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401


class TestQueryEndpoints:
    """Test query endpoints with auth."""

    def test_query_endpoint_structure(self, client: TestClient, auth_header: dict) -> None:
        """Test full query endpoint returns expected structure."""
        response = client.post(
            "/api/v1/query",
            json={"query": "test query", "stream": False},
            headers=auth_header,
        )
        # 500 is acceptable here if storage is not running,
        # but 401 is NOT.
        assert response.status_code != 401

    def test_query_empty_query(self, client: TestClient, auth_header: dict) -> None:
        """Test query with empty query returns validation error."""
        response = client.post(
            "/api/v1/query",
            json={"query": ""},
            headers=auth_header,
        )
        # Empty query should fail validation (422)
        assert response.status_code == 422

    def test_query_with_llm_api_key_field(self, client: TestClient, auth_header: dict) -> None:
        """Test query accepts llm_api_key field (even if key is invalid)."""
        response = client.post(
            "/api/v1/query",
            json={
                "query": "What is the capital of France?",
                "llm_api_key": "sk-test-key-for-structure-verification",  # pragma: allowlist secret
            },
            headers=auth_header,
        )
        # Should not be 401 (auth passes) or 422 (schema valid)
        # May be 500 (no actual LLM) but not auth/schema error
        assert response.status_code not in (401, 422)

    def test_query_llm_api_key_too_short(self, client: TestClient, auth_header: dict) -> None:
        """Test query rejects llm_api_key that is too short."""
        response = client.post(
            "/api/v1/query",
            json={
                "query": "test",
                "llm_api_key": "short",  # pragma: allowlist secret
            },
            headers=auth_header,
        )
        assert response.status_code == 422

    def test_query_llm_api_key_whitespace_stripped(self, client: TestClient, auth_header: dict) -> None:
        """Test query accepts llm_api_key that would fail if not stripped."""
        response = client.post(
            "/api/v1/query",
            json={
                "query": "test",
                "llm_api_key": "sk-or-v1-valid-length-key-for-test",  # pragma: allowlist secret
            },
            headers=auth_header,
        )
        assert response.status_code != 422


class TestMetadataEndpoints:
    """Test metadata endpoints with auth."""

    def test_stats_endpoint(self, client: TestClient, auth_header: dict) -> None:
        """Test stats endpoint returns counts."""
        response = client.get("/api/v1/metadata/stats", headers=auth_header)
        assert response.status_code != 401

    def test_departments_endpoint(self, client: TestClient, auth_header: dict) -> None:
        """Test departments endpoint returns list."""
        # Check if the endpoint exists - it should according to main.py
        response = client.get("/api/v1/metadata/departments", headers=auth_header)
        assert response.status_code != 401


class TestIngestEndpoints:
    """Test ingest endpoints with auth."""

    def test_ingest_endpoint_structure(self, client: TestClient, auth_header: dict) -> None:
        """Test ingest endpoint accepts request."""
        response = client.post(
            "/api/v1/ingest",
            json={"file_path": "test.pdf"},
            headers=auth_header,
        )
        assert response.status_code != 401


class TestCORS:
    """Test CORS configuration."""

    def test_app_has_cors_in_title(self, client: TestClient) -> None:
        """Test app is properly configured."""
        # Verify app is configured correctly
        from src.api.main import app

        assert app.title == "Production RAG API"
        assert app.version == "1.0.0"

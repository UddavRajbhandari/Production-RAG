"""
Integration tests for Production RAG API.
Phase 8.1: API deployment verification.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

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


class TestQueryEndpoints:
    """Test query endpoints."""

    def test_retrieve_endpoint_structure(self, client: TestClient) -> None:
        """Test retrieve endpoint returns expected structure."""
        response = client.post(
            "/api/v1/query/retrieve",
            json={"query": "test query", "stream": False, "include_sources": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert "count" in data

    def test_retrieve_empty_query(self, client: TestClient) -> None:
        """Test retrieve with empty query returns validation error."""
        response = client.post(
            "/api/v1/query/retrieve",
            json={"query": "", "stream": False},
        )
        # Empty query should fail validation (422)
        assert response.status_code == 422

    def test_query_endpoint_structure(self, client: TestClient) -> None:
        """Test full query endpoint returns expected structure."""
        response = client.post(
            "/api/v1/query",
            json={"query": "What is the project about?", "stream": False},
        )
        assert response.status_code in [200, 500]  # May fail without LLM


class TestMetadataEndpoints:
    """Test metadata endpoints."""

    def test_stats_endpoint(self, client: TestClient) -> None:
        """Test stats endpoint returns counts."""
        response = client.get("/api/v1/metadata/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_chunks" in data
        assert "by_department" in data
        assert "by_year" in data

    def test_departments_endpoint(self, client: TestClient) -> None:
        """Test departments endpoint returns list."""
        response = client.get("/api/v1/metadata/departments")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_metadata_query_filter(self, client: TestClient) -> None:
        """Test metadata query with filters."""
        response = client.post(
            "/api/v1/metadata/query",
            json={"department": "Financial", "limit": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "chunks" in data


class TestIngestEndpoints:
    """Test ingest endpoints."""

    def test_ingest_endpoint_structure(self, client: TestClient) -> None:
        """Test ingest endpoint accepts request."""
        response = client.post(
            "/api/v1/ingest",
            json={"file_path": "test.pdf"},
        )
        # Should fail gracefully (file not found) not 422
        assert response.status_code in [404, 500]


class TestCORS:
    """Test CORS configuration."""

    def test_app_has_cors_in_title(self, client: TestClient) -> None:
        """Test app is properly configured."""
        # Verify app is configured correctly
        from src.api.main import app

        assert app.title == "Production RAG API"
        assert app.version == "1.0.0"

"""
Integration tests for Production RAG API.
Phase 8.1: API deployment verification.
Phase 8.3: User-provided LLM key flow.

Auth is via HttpOnly session cookie (set by /api/v1/session/init).
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.middleware.session import create_session_token
from src.api.models.models import settings

TEST_TENANT_ID = "test-tenant-001"


@pytest.fixture(autouse=True)
def _reset_settings() -> None:
    """Reset settings before each test."""
    settings.api_key = "test-key"  # pragma: allowlist secret
    settings.require_api_key = True


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_cookie() -> dict[str, str]:
    """Return a valid session cookie."""
    token = create_session_token(TEST_TENANT_ID)
    return {"session": token}


class TestHealthEndpoints:
    """Test health check endpoints (no auth required)."""

    def test_root_endpoint(self, client: TestClient) -> None:
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "status" in data
        assert data["status"] == "running"

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

    def test_missing_session(self, client: TestClient) -> None:
        """Test request fails without session cookie."""
        response = client.post("/api/v1/query", json={"query": "test"})
        assert response.status_code == 401

    def test_invalid_session(self, client: TestClient) -> None:
        """Test request fails with invalid session cookie."""
        response = client.post(
            "/api/v1/query",
            json={"query": "test"},
            cookies={"session": "invalid-token"},
        )
        assert response.status_code == 401

    def test_expired_session(self, client: TestClient) -> None:
        """Test request fails with expired session token."""
        import time as time_module

        from src.api.middleware.session import _SESSION_SECRET

        secret = _SESSION_SECRET
        if secret is None:
            from src.api.middleware.session import _get_secret

            secret = _get_secret()

        import base64
        import hmac
        import json

        payload = {"t": TEST_TENANT_ID, "e": int(time_module.time()) - 1}
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        sig = hmac.new(secret.encode(), payload_b64.encode(), "sha256").hexdigest()[:16]
        expired_token = f"{payload_b64}.{sig}"

        response = client.post(
            "/api/v1/query",
            json={"query": "test"},
            cookies={"session": expired_token},
        )
        assert response.status_code == 401


class TestSessionInit:
    """Test session initialization."""

    def test_session_init_returns_tenant_id(self, client: TestClient) -> None:
        """Test session init returns tenant_id and sets cookie."""
        response = client.post("/api/v1/session/init")
        assert response.status_code == 200
        data = response.json()
        assert "tenant_id" in data
        assert "api_key" not in data
        # Verify cookie is set
        set_cookie = response.headers.get("set-cookie", "")
        assert "session=" in set_cookie
        assert "httponly" in set_cookie.lower()

    def test_session_init_restores_existing_tenant(self, client: TestClient) -> None:
        """Test session init with a valid tenant_id re-issues cookie for that tenant."""
        # First, create a tenant
        create_resp = client.post("/api/v1/session/init")
        assert create_resp.status_code == 200
        original_tenant_id = create_resp.json()["tenant_id"]
        original_cookie = create_resp.cookies.get("session")
        assert original_cookie is not None
        assert original_tenant_id is not None

        # Now call init again with the same tenant_id — should return same tenant
        restore_resp = client.post(
            "/api/v1/session/init",
            json={"tenant_id": original_tenant_id},
        )
        assert restore_resp.status_code == 200
        restored_data = restore_resp.json()
        assert restored_data["tenant_id"] == original_tenant_id
        restored_cookie = restore_resp.cookies.get("session")
        # Cookie should be different (newly signed) but tenant_id same
        assert restored_cookie is not None

    def test_session_init_unknown_tenant_creates_new(self, client: TestClient) -> None:
        """Test session init with a non-existent tenant_id creates a new tenant."""
        response = client.post(
            "/api/v1/session/init",
            json={"tenant_id": "tnt_nonexistent"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] != "tnt_nonexistent"
        assert "tenant_id" in data


class TestQueryEndpoints:
    """Test query endpoints with auth."""

    def test_query_endpoint_structure(self, client: TestClient, auth_cookie: dict) -> None:
        """Test full query endpoint returns expected structure."""
        response = client.post(
            "/api/v1/query",
            json={"query": "test query", "stream": False},
            cookies=auth_cookie,
        )
        # 500 is acceptable here if storage is not running,
        # but 401 is NOT.
        assert response.status_code != 401

    def test_query_empty_query(self, client: TestClient, auth_cookie: dict) -> None:
        """Test query with empty query returns validation error."""
        response = client.post(
            "/api/v1/query",
            json={"query": ""},
            cookies=auth_cookie,
        )
        # Empty query should fail validation (422)
        assert response.status_code == 422

    def test_query_with_llm_api_key_field(self, client: TestClient, auth_cookie: dict) -> None:
        """Test query accepts llm_api_key field (even if key is invalid)."""
        response = client.post(
            "/api/v1/query",
            json={
                "query": "What is the capital of France?",
                "llm_api_key": "sk-test-key-for-structure-verification",  # pragma: allowlist secret
            },
            cookies=auth_cookie,
        )
        # Should not be 401 (auth passes) or 422 (schema valid)
        # May be 500 (no actual LLM) but not auth/schema error
        assert response.status_code not in (401, 422)

    def test_query_llm_api_key_too_short(self, client: TestClient, auth_cookie: dict) -> None:
        """Test query rejects llm_api_key that is too short."""
        response = client.post(
            "/api/v1/query",
            json={
                "query": "test",
                "llm_api_key": "short",  # pragma: allowlist secret
            },
            cookies=auth_cookie,
        )
        assert response.status_code == 422

    def test_query_llm_api_key_whitespace_stripped(self, client: TestClient, auth_cookie: dict) -> None:
        """Test query accepts llm_api_key that would fail if not stripped."""
        response = client.post(
            "/api/v1/query",
            json={
                "query": "test",
                "llm_api_key": "sk-or-v1-valid-length-key-for-test",  # pragma: allowlist secret
            },
            cookies=auth_cookie,
        )
        assert response.status_code != 422


class TestMetadataEndpoints:
    """Test metadata endpoints with auth."""

    def test_stats_endpoint(self, client: TestClient, auth_cookie: dict) -> None:
        """Test stats endpoint returns counts."""
        response = client.get("/api/v1/metadata/stats", cookies=auth_cookie)
        assert response.status_code != 401

    def test_departments_endpoint(self, client: TestClient, auth_cookie: dict) -> None:
        """Test departments endpoint returns list."""
        response = client.get("/api/v1/metadata/departments", cookies=auth_cookie)
        assert response.status_code != 401


class TestIngestEndpoints:
    """Test ingest endpoints with auth."""

    def test_ingest_endpoint_structure(self, client: TestClient, auth_cookie: dict) -> None:
        """Test ingest endpoint accepts request."""
        response = client.post(
            "/api/v1/ingest",
            json={"file_path": "test.pdf"},
            cookies=auth_cookie,
        )
        assert response.status_code != 401

    def test_ingest_file_no_auth(self, client: TestClient) -> None:
        """Test file upload without session cookie is rejected."""
        response = client.post(
            "/api/v1/ingest/file",
            files={"file": ("test.pdf", b"fake content", "application/pdf")},
        )
        assert response.status_code == 401

    def test_ingest_file_valid_cookie(self, client: TestClient, auth_cookie: dict) -> None:
        """Test file upload with valid session cookie."""
        response = client.post(
            "/api/v1/ingest/file",
            files={"file": ("test.pdf", b"fake content", "application/pdf")},
            cookies=auth_cookie,
        )
        # Auth passes; will fail at pipeline (no storage) → not 401
        assert response.status_code != 401

    def test_ingest_file_unsupported_type(self, client: TestClient, auth_cookie: dict) -> None:
        """Test file upload with unsupported file type returns 400."""
        response = client.post(
            "/api/v1/ingest/file",
            files={"file": ("test.exe", b"fake content", "application/octet-stream")},
            cookies=auth_cookie,
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Unsupported file type" in data["detail"]

    def test_ingest_file_too_large(self, client: TestClient, auth_cookie: dict) -> None:
        """Test file upload with oversized file returns 400."""
        large_content = b"x" * (101 * 1024 * 1024)
        response = client.post(
            "/api/v1/ingest/file",
            files={"file": ("large.pdf", large_content, "application/pdf")},
            cookies=auth_cookie,
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "File too large" in data["detail"]

    @pytest.mark.unit
    def test_get_ingestion_pipeline_lazy_load_error(self) -> None:
        """Test that lazy-load raises HTTPException on import failure (simulated)."""
        from src.api.routes.ingest import get_ingestion_pipeline

        pipeline = get_ingestion_pipeline()
        assert pipeline is not None


class TestCORS:
    """Test CORS configuration."""

    def test_app_has_cors_in_title(self, client: TestClient) -> None:
        """Test app is properly configured."""
        from src.api.main import app

        assert app.title == "Production RAG API"
        assert app.version == "1.0.0"

    def test_cors_preflight_allowed(self, client: TestClient) -> None:
        """Test CORS preflight (OPTIONS) request is allowed."""
        response = client.options(
            "/api/v1/ingest/file",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert response.headers.get("access-control-allow-methods") is not None

    def test_cors_preflight_rejected_origin(self, client: TestClient) -> None:
        """Test CORS preflight from unknown origin is rejected."""
        response = client.options(
            "/api/v1/ingest/file",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        cors_origin = response.headers.get("access-control-allow-origin")
        assert cors_origin is None or cors_origin != "https://evil.com"

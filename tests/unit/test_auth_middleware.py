"""Tests for the API auth middleware (verify_api_key).

Covers:
  - Session cookie auth (primary)
  - X-Tenant-ID header fallback (for cross-origin file uploads)
  - Exempt endpoints (health, session)
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request

from src.api.middleware.auth import verify_api_key
from src.api.middleware.session import create_session_token

TEST_TENANT_ID = "tnt_test_abc123"


@pytest.fixture
def req() -> MagicMock:
    mock = MagicMock(spec=Request)
    mock.url.path = "/api/v1/query"
    mock.cookies = {}
    mock.headers = {}
    # Use a plain object so attribute assignment sticks
    mock.state = MagicMock()
    return mock


class TestSessionCookieAuth:
    """Primary auth path: HttpOnly session cookie."""

    @pytest.mark.asyncio
    async def test_valid_cookie_passes(self, req: MagicMock) -> None:
        req.cookies = {"session": create_session_token(TEST_TENANT_ID)}
        result = await verify_api_key(req)
        assert result is not None
        assert req.state.tenant_id == TEST_TENANT_ID

    @pytest.mark.asyncio
    async def test_missing_cookie_raises_401(self, req: MagicMock) -> None:
        with pytest.raises(HTTPException) as exc:
            await verify_api_key(req)
        assert exc.value.status_code == 401
        assert exc.value.detail["error"] == "not_authenticated"

    @pytest.mark.asyncio
    async def test_invalid_cookie_raises_401(self, req: MagicMock) -> None:
        req.cookies = {"session": "garbage.token"}
        with pytest.raises(HTTPException) as exc:
            await verify_api_key(req)
        assert exc.value.status_code == 401
        assert exc.value.detail["error"] == "invalid_session"


class TestTenantIdHeaderFallback:
    """Fallback auth path: X-Tenant-ID header (cross-origin uploads)."""

    @pytest.mark.asyncio
    @patch("src.storage.tenant_store.get_tenant_store")
    async def test_valid_tenant_id_header_passes(self, mock_get_store: MagicMock, req: MagicMock) -> None:
        mock_store = MagicMock()
        mock_store.tenant_exists.return_value = True
        mock_get_store.return_value = mock_store

        req.headers = {"X-Tenant-ID": TEST_TENANT_ID}
        result = await verify_api_key(req)
        assert result == TEST_TENANT_ID
        assert req.state.tenant_id == TEST_TENANT_ID
        mock_store.tenant_exists.assert_called_once_with(TEST_TENANT_ID)

    @pytest.mark.asyncio
    @patch("src.storage.tenant_store.get_tenant_store")
    async def test_unknown_tenant_id_raises_401(self, mock_get_store: MagicMock, req: MagicMock) -> None:
        mock_store = MagicMock()
        mock_store.tenant_exists.return_value = False
        mock_get_store.return_value = mock_store

        req.headers = {"X-Tenant-ID": "tnt_nonexistent"}
        with pytest.raises(HTTPException) as exc:
            await verify_api_key(req)
        assert exc.value.status_code == 401
        assert exc.value.detail["error"] == "invalid_tenant"
        assert "tnt_nonexistent" in exc.value.detail["message"]
        mock_store.tenant_exists.assert_called_once_with("tnt_nonexistent")

    @pytest.mark.asyncio
    async def test_missing_header_raises_401_when_no_cookie(self, req: MagicMock) -> None:
        with pytest.raises(HTTPException) as exc:
            await verify_api_key(req)
        assert exc.value.status_code == 401
        assert exc.value.detail["error"] == "not_authenticated"

    @pytest.mark.asyncio
    @patch("src.storage.tenant_store.get_tenant_store")
    async def test_cookie_takes_precedence_over_header(self, mock_get_store: MagicMock, req: MagicMock) -> None:
        mock_store = MagicMock()
        mock_store.tenant_exists.return_value = True
        mock_get_store.return_value = mock_store

        valid_token = create_session_token(TEST_TENANT_ID)
        req.cookies = {"session": valid_token}
        req.headers = {"X-Tenant-ID": "header_tenant"}
        result = await verify_api_key(req)
        assert result == valid_token
        assert req.state.tenant_id == TEST_TENANT_ID
        mock_store.tenant_exists.assert_not_called()


class TestExemptEndpoints:
    """Endpoints that skip auth entirely."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/health",
            "/api/v1/health/live",
            "/api/v1/health/ready",
            "/api/v1/session/init",
            "/health/",
        ],
    )
    async def test_exempt_path_returns_empty_string(self, req: MagicMock, path: str) -> None:
        req.url.path = path
        result = await verify_api_key(req)
        assert result == ""

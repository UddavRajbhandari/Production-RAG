"""Tests for api_llm_client.py — 401 Unauthorized detection.

Covers:
  - InvalidAPIKeyError raised on 401 response
  - Other HTTP errors raised as httpx.HTTPStatusError
  - Successful responses parsed correctly
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.reasoning.utils.api_llm_client import (
    APIConfig,
    APILLMClient,
    InvalidAPIKeyError,
)


@pytest.fixture
def config() -> APIConfig:
    return APIConfig(
        endpoint="https://openrouter.ai/api/v1/chat/completions",
        api_key="test-key",  # pragma: allowlist secret
        model="test-model",
        timeout=10,
    )


@pytest.fixture
def client(config: APIConfig) -> APILLMClient:
    return APILLMClient(config)


class TestInvalidAPIKeyError:
    """401 Unauthorized → InvalidAPIKeyError (no retry)."""

    def test_401_raises_invalid_api_key_error(self, client: APILLMClient) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid API key", "code": 401}}
        mock_response.request = MagicMock(spec=httpx.Request)

        with patch.object(client.client, "post", return_value=mock_response):
            with pytest.raises(InvalidAPIKeyError) as exc_info:
                client.generate("test prompt")
            assert exc_info.value.status_code == 401
            assert "openrouter.ai" in str(exc_info.value)

    def test_401_does_not_retry(self, client: APILLMClient) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Unauthorized"}}
        mock_response.request = MagicMock(spec=httpx.Request)

        with patch.object(client.client, "post", return_value=mock_response) as mock_post:
            with pytest.raises(InvalidAPIKeyError):
                client.generate("test prompt")
            # Should only be called once — no retries for 401
            assert mock_post.call_count == 1


class TestOtherHTTPErrors:
    """Non-401 errors should still raise httpx.HTTPStatusError."""

    def test_500_raises_http_status_error(self, client: APILLMClient) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": {"message": "Internal error"}}
        mock_response.request = MagicMock(spec=httpx.Request)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=mock_response.request, response=mock_response
        )

        with patch.object(client.client, "post", return_value=mock_response), pytest.raises(httpx.HTTPStatusError):
            client.generate("test prompt")


class TestSuccessfulResponse:
    """Valid API key → successful response."""

    def test_valid_key_returns_success(self, client: APILLMClient) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "Hello!"}}]}
        mock_response.raise_for_status.return_value = None

        with patch.object(client.client, "post", return_value=mock_response):
            result = client.generate("test prompt")
            assert result["success"] is True
            assert result["text"] == "Hello!"

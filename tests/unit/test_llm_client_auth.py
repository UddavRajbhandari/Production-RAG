"""Tests for llm_client.py — invalid API key error propagation.

Covers:
  - User-provided invalid key returns LLMResponse with invalid_api_key error
  - System API key failure is caught and logged
  - Error message is user-friendly
"""

from unittest.mock import MagicMock, patch

import pytest

from src.reasoning.utils.api_llm_client import InvalidAPIKeyError
from src.reasoning.utils.llm_client import LLMClient


@pytest.fixture
def mock_llm_client() -> LLMClient:
    """Create an LLMClient with mocked config to avoid real API calls."""
    with patch("src.reasoning.utils.llm_client.ConfigLoader") as mock_config_cls:
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "llm.provider": "auto",
            "llm.profiles": {
                "openrouter": {
                    "type": "api",
                    "env_key": "OPENROUTER_API_KEY",
                    "endpoint": "https://openrouter.ai/api/v1/chat/completions",
                    "model": "test-model",
                    "timeout": 10,
                }
            },
        }.get(key, default)
        mock_config_cls.return_value = mock_config
        client = LLMClient.__new__(LLMClient)
        client.config = mock_config
        client.max_retries = 3
        client.timeout = 10
        client.circuit_breaker = MagicMock()
        client._api_client = None
        client.active_profile = "unknown"
        client._ollama_cache = None
        client._OLLAMA_CACHE_TTL = 30
        return client


class TestUserProvidedInvalidKey:
    """User provides an invalid OpenRouter API key → clear error message."""

    def test_invalid_key_returns_error_response(self, mock_llm_client: LLMClient) -> None:
        with patch("src.reasoning.utils.api_llm_client.APILLMClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.generate.side_effect = InvalidAPIKeyError("openrouter.ai", 401)

            result = mock_llm_client.generate("test", llm_api_key="invalid-key-12345")

            assert result.success is False
            assert result.error is not None
            assert "invalid_api_key" in result.error
            assert "invalid or expired" in result.error.lower()

    def test_invalid_key_does_not_use_system_key(self, mock_llm_client: LLMClient) -> None:
        """When user key fails with 401, should NOT fall back to system key."""
        with patch("src.reasoning.utils.api_llm_client.APILLMClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.generate.side_effect = InvalidAPIKeyError("openrouter.ai", 401)

            result = mock_llm_client.generate("test", llm_api_key="bad-key")

            # Should return immediately with error, not try other providers
            assert result.success is False
            assert result.error is not None
            assert "invalid_api_key" in result.error

    def test_invalid_key_latency_is_zero(self, mock_llm_client: LLMClient) -> None:
        with patch("src.reasoning.utils.api_llm_client.APILLMClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.generate.side_effect = InvalidAPIKeyError("openrouter.ai", 401)

            result = mock_llm_client.generate("test", llm_api_key="bad-key")

            assert result.latency_ms == 0.0


class TestSystemAPIKeyInvalid:
    """System API key returns 401 → circuit breaker records failure."""

    def test_system_invalid_key_records_failure(self, mock_llm_client: LLMClient) -> None:
        mock_llm_client.provider = "api"
        mock_llm_client.active_profile = "openrouter"
        mock_llm_client._api_client = MagicMock()
        mock_llm_client._api_client.generate.side_effect = InvalidAPIKeyError("openrouter.ai", 401)

        with patch("src.reasoning.utils.llm_client.os.getenv", return_value="system-key"):
            mock_llm_client.generate("test")

            mock_llm_client.circuit_breaker.record_failure.assert_called()  # type: ignore[attr-defined]

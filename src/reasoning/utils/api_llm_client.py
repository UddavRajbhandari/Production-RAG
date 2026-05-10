"""
API LLM Client
Flexible client for any OpenAI-compatible API endpoint.
Supports: OpenAI, Anthropic (adapter), LM Studio, Ollama (v1), etc.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from src.reasoning.utils.json_parser import safe_json_parse

logger = logging.getLogger(__name__)


@dataclass
class APIConfig:
    """Configuration for API-based LLM client."""

    endpoint: str
    api_key: str
    model: str
    timeout: int = 120


class APILLMClient:
    """Provider-agnostic LLM client using OpenAI-compatible API format."""

    def __init__(self, config: APIConfig) -> None:
        self.config = config
        self.client = httpx.Client(timeout=config.timeout)

    def generate(
        self,
        prompt: str,
        format_json: bool = False,
        temperature: float = 0.0,
        custom_model: str | None = None,
    ) -> dict[str, Any]:
        """
        Call any OpenAI-compatible endpoint.

        Args:
            prompt: The prompt to send
            format_json: Whether to request JSON response
            temperature: Sampling temperature
            custom_model: Optional model override

        Returns:
            Dict with text, latency_ms, and success status
        """
        start_time = time.perf_counter()
        model = custom_model or self.config.model

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        # Build payload - OpenAI format
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }

        # Request JSON format if needed
        if format_json:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = self.client.post(
                self.config.endpoint,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract text from response
            text = ""
            if "choices" in result and len(result["choices"]) > 0:
                text = result["choices"][0].get("message", {}).get("content", "")

            return {
                "text": text,
                "raw_response": result,
                "latency_ms": latency_ms,
                "success": True,
                "error": None,
            }

        except httpx.TimeoutException:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(f"API request timeout after {latency_ms:.0f}ms")
            return {
                "text": "",
                "raw_response": {},
                "latency_ms": latency_ms,
                "success": False,
                "error": f"Timeout after {self.config.timeout}s",
            }
        except httpx.HTTPStatusError as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            error_msg = f"API HTTP error: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            return {
                "text": "",
                "raw_response": {},
                "latency_ms": latency_ms,
                "success": False,
                "error": f"HTTP {e.response.status_code}",
            }
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"API request failed: {e}")
            return {
                "text": "",
                "raw_response": {},
                "latency_ms": latency_ms,
                "success": False,
                "error": str(e),
            }

    def generate_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate and parse JSON response."""
        result = self.generate(prompt, format_json=True, temperature=temperature)
        if not result["success"]:
            logger.error(f"JSON generation failed: {result['error']}")
            return default or {}
        return safe_json_parse(result["text"], default)

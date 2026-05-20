"""
API LLM Client
Flexible client for any OpenAI-compatible API endpoint.
Supports: OpenAI, Anthropic (adapter), LM Studio, Ollama (v1), etc.
"""

import logging
import re
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

        # Detect HuggingFace endpoint and use appropriate format
        is_huggingface = "huggingface.co" in self.config.endpoint

        if is_huggingface:
            # HuggingFace format
            payload: dict[str, Any] = {
                "inputs": prompt,
                "parameters": {
                    "temperature": temperature,
                    "max_new_tokens": self.config.timeout * 2,
                },
            }
        else:
            # OpenAI-compatible format
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
            if format_json:
                payload["response_format"] = {"type": "json_object"}

        # Retry logic for rate limiting
        max_retries = 3
        result = None

        for attempt in range(max_retries):
            try:
                response = self.client.post(
                    self.config.endpoint,
                    json=payload,
                    headers=headers,
                )

                # Handle rate limiting (429) with retry
                if response.status_code == 429:
                    # Extract retry-after from response or error message
                    retry_after = 30  # default
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", "")
                        # Try to extract seconds from message: "try again in 15.735s"
                        match = re.search(r"try again in ([\d.]+)s", error_msg)
                        if match:
                            retry_after = int(float(match.group(1))) + 1  # add buffer
                        else:
                            # Check headers
                            retry_after = int(response.headers.get("retry-after", 30))
                    except Exception:
                        pass

                    if attempt < max_retries - 1:
                        logger.info(
                            f"Rate limited (429), waiting {retry_after}s before retry {attempt + 2}/{max_retries}..."
                        )
                        time.sleep(retry_after)
                        continue
                    else:
                        # All retries exhausted
                        raise httpx.HTTPStatusError(
                            "Rate limit exceeded after retries",
                            request=response.request,
                            response=response,
                        )

                response.raise_for_status()
                result = response.json()
                break  # Success, exit retry loop

            except httpx.HTTPStatusError:
                if response.status_code == 429 and attempt < max_retries - 1:
                    logger.info(f"Rate limited (429), retrying in {5 * (attempt + 1)}s...")
                    time.sleep(5 * (attempt + 1))  # short backoff
                    continue
                raise
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    logger.warning("Timeout, retrying...")
                    time.sleep(2 * (attempt + 1))
                    continue
                raise

        # Process result after successful response
        if result is None:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return {
                "text": "",
                "raw_response": {},
                "latency_ms": latency_ms,
                "success": False,
                "error": "Max retries exceeded",
            }

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Extract text from response
        text = ""
        if is_huggingface:
            # HuggingFace format: [{"generated_text": "..."}]
            if isinstance(result, list) and len(result) > 0:
                text = result[0].get("generated_text", "")
            elif "generated_text" in result:
                text = result.get("generated_text", "")
        else:
            # OpenAI format
            if "choices" in result and len(result["choices"]) > 0:
                text = result["choices"][0].get("message", {}).get("content", "")

        return {
            "text": text,
            "raw_response": result,
            "latency_ms": latency_ms,
            "success": True,
            "error": None,
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

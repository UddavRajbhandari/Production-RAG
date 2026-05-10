"""
LLM Client
Centralized LLM API calls with support for both Ollama (local) and external APIs.
Uses retry logic and circuit breaker pattern.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

if TYPE_CHECKING:
    pass

import requests

from src.reasoning.utils.config_loader import ConfigLoader
from src.reasoning.utils.json_parser import safe_json_parse

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Structured LLM response."""

    text: str
    raw_response: dict[str, Any]
    latency_ms: float
    success: bool
    error: str | None = None


class CircuitBreaker:
    """Circuit breaker pattern to prevent repeated failing calls."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 60) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.last_failure_time: float | None = None
        self.is_open = False

    def record_success(self) -> None:
        """Record a successful call."""
        self.failures = 0
        self.is_open = False

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.is_open = True
            logger.warning(
                f"Circuit breaker opened after {self.failures} consecutive failures"
            )

    def can_proceed(self) -> bool:
        """Check if calls can proceed."""
        if not self.is_open:
            return True
        if self.last_failure_time is None:
            return True
        if time.time() - self.last_failure_time > self.cooldown_seconds:
            logger.info("Circuit breaker cooling down, allowing attempt")
            self.is_open = False
            return True
        return False


class LLMClient:
    """
    Unified LLM client with Dynamic Provider Detection.
    Automatically selects the best available provider based on environment keys.
    """

    def __init__(
        self,
        config_path: str = "config/settings.yaml",
        max_retries: int = 3,
        timeout: int = 120,
    ) -> None:
        self.config = ConfigLoader(config_path)
        self.max_retries = max_retries
        self.timeout = timeout
        self.circuit_breaker = CircuitBreaker()
        self._api_client: Any = None
        self.active_profile: str = "unknown"

        self._select_provider()

    def _select_provider(self) -> None:
        """Selects and initializes the LLM provider based on config and env."""
        requested_provider = str(self.config.get("llm.provider", "auto"))
        profiles = cast(dict[str, Any], self.config.get("llm.profiles", {}))

        if requested_provider == "auto":
            # Priority-based auto-detection
            priority_list = ["groq", "openai", "openrouter", "huggingface", "ollama"]
            for profile_name in priority_list:
                if self._try_init_profile(profile_name, profiles.get(profile_name)):
                    return

            # If all else fails, use a fallback error state
            logger.critical("No valid LLM providers detected. Set an API key in .env")
        else:
            # Explicit selection
            profile = profiles.get(requested_provider)
            if not self._try_init_profile(requested_provider, profile):
                logger.error(
                    f"Failed to initialize requested provider: {requested_provider}"
                )

    def _try_init_profile(self, name: str, profile: dict | None) -> bool:
        """Attempts to initialize a specific provider profile."""
        if not profile:
            return False

        profile_type = profile.get("type")

        if profile_type == "api":
            env_key = profile.get("env_key", "")
            api_key = os.getenv(env_key, "")

            if api_key:
                try:
                    from src.reasoning.utils.api_llm_client import (
                        APIConfig,
                        APILLMClient,
                    )

                    config = APIConfig(
                        endpoint=profile.get("endpoint", ""),
                        api_key=api_key,
                        model=profile.get("model", ""),
                        timeout=profile.get("timeout", self.timeout),
                    )
                    self._api_client = APILLMClient(config)
                    self.provider = "api"
                    self.active_profile = name
                    self.timeout = config.timeout
                    logger.info(f"LLM Client: Auto-detected '{name}' via {env_key}")
                    return True
                except Exception as e:
                    logger.warning(f"Failed to init {name} profile: {e}")
                    return False

        elif profile_type == "ollama":
            url = profile.get("url", "http://localhost:11434/api/generate")
            # Minimal reachability check
            try:
                # We don't want to wait too long for a check
                resp = requests.get(
                    url.replace("/api/generate", "/api/tags"), timeout=2
                )
                if resp.status_code == 200:
                    self._ollama_url = url
                    self._ollama_model = profile.get("model", "llama3")
                    self.provider = "ollama"
                    self.active_profile = name
                    self.timeout = profile.get("timeout", self.timeout)
                    logger.info(f"LLM Client: Auto-detected local Ollama at {url}")
                    return True
            except Exception:
                logger.debug(f"Ollama profile '{name}' not reachable at {url}")
                return False

        return False

    def generate(
        self,
        prompt: str,
        format_json: bool = False,
        temperature: float = 0.0,
        custom_model: str | None = None,
    ) -> LLMResponse:
        """Generates a response using the active provider."""
        if not self.circuit_breaker.can_proceed():
            return LLMResponse("", {}, 0.0, False, "Circuit breaker open")

        if self.provider == "api":
            result = self._api_client.generate(
                prompt, format_json, temperature, custom_model
            )
            if result["success"]:
                self.circuit_breaker.record_success()
            else:
                self.circuit_breaker.record_failure()
            return LLMResponse(
                text=result["text"],
                raw_response=result["raw_response"],
                latency_ms=result["latency_ms"],
                success=result["success"],
                error=result["error"],
            )
        else:
            return self._generate_ollama(prompt, format_json, temperature, custom_model)

    def _generate_ollama(
        self,
        prompt: str,
        format_json: bool,
        temperature: float,
        custom_model: str | None,
    ) -> LLMResponse:
        """Generate using Ollama."""
        model = custom_model or self._ollama_model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format_json:
            payload["format"] = "json"

        last_error = None
        for attempt in range(self.max_retries):
            start_time = time.perf_counter()
            try:
                response = requests.post(
                    self._ollama_url, json=payload, timeout=self.timeout
                )
                response.raise_for_status()
                result = response.json()
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.circuit_breaker.record_success()
                return LLMResponse(result.get("response", ""), result, latency_ms, True)
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    time.sleep((2**attempt) * 0.5)

        self.circuit_breaker.record_failure()
        return LLMResponse("", {}, 0.0, False, last_error or "Max retries exceeded")

    def generate_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate and parse JSON response."""
        response = self.generate(prompt, format_json=True, temperature=temperature)
        if not response.success:
            return default or {}
        return safe_json_parse(response.text, default)

"""
Configuration Loader
Singleton pattern to load config.yaml once and provide typed access.
"""

import threading
from pathlib import Path
from typing import Any

import yaml


class ConfigLoader:
    """Singleton configuration loader for the reasoning engine."""

    _instance: "ConfigLoader | None" = None
    _lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls, config_path: str = "config/settings.yaml") -> "ConfigLoader":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._initialized = False
        return cls._instance

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        if ConfigLoader._initialized:
            return
        ConfigLoader._initialized = True
        self._config_path = config_path
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        path = Path(self._config_path)
        if not path.exists():
            path = Path(__file__).parent.parent.parent.parent / self._config_path
        with open(path) as f:
            self._config = yaml.safe_load(f)

    @property
    def model_name(self) -> str:
        models = self._config.get("models", {})
        return str(models.get("llm_local", "llama3:8b-instruct-q4_K_M"))

    @property
    def ollama_url(self) -> str:
        return "http://localhost:11434/api/generate"

    @property
    def latency_budget_ms(self) -> int:
        latency = self._config.get("latency", {})
        return int(latency.get("total_p95_ms", 180000))

    @property
    def generation_budget_ms(self) -> int:
        latency = self._config.get("latency", {})
        return int(latency.get("generation_budget_ms", 150000))

    def get_optional(self, key: str, default: str = "") -> str:
        """Get optional string config with default."""
        keys = key.split(".")
        value: Any = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return str(value) if value else default

    def get(self, key: str, default: "object | None" = None) -> "object | None":
        """
        Get nested config value using dot notation.
        Example: get("llm.api.endpoint") returns config["llm"]["api"]["endpoint"]
        """
        keys = key.split(".")
        value: Any = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value if value is not None else default

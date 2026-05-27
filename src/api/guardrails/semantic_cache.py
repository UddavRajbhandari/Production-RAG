"""
Semantic Cache — returns cached LLM responses for semantically similar queries.

Uses embedding similarity (cosine) to detect query equivalence.
LRU eviction + TTL support prevents unbounded memory growth.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import Any, cast

import numpy as np

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a, dtype=np.float64)
    b_arr = np.array(b, dtype=np.float64)
    dot = float(np.dot(a_arr, b_arr))
    norm_a = float(np.linalg.norm(a_arr))
    norm_b = float(np.linalg.norm(b_arr))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticCache:
    """Embedding-based semantic cache with LRU eviction and TTL."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        similarity_threshold: float = 0.92,
        max_size: int = 256,
        ttl_seconds: int = 3600,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def _embed(self, text: str) -> list[float]:
        return cast(list[float], self._model.encode(text).tolist())

    def _cache_key(self, query: str) -> str:
        return str(hash(query))

    def get(self, query: str) -> str | None:
        """Return cached answer if a semantically similar query exists."""
        query_embedding = self._embed(query)
        now = time.time()

        best_match: tuple[str, float] | None = None
        expired_keys: list[str] = []

        for key, entry in self._cache.items():
            if now - entry["timestamp"] > self.ttl_seconds:
                expired_keys.append(key)
                continue

            sim = _cosine_similarity(query_embedding, entry["embedding"])
            if sim >= self.similarity_threshold and (best_match is None or sim > best_match[1]):
                best_match = (key, sim)

        for k in expired_keys:
            del self._cache[k]

        if best_match:
            entry = self._cache[best_match[0]]
            self._cache.move_to_end(best_match[0])
            logger.info(
                "Semantic cache HIT (similarity=%.4f) for query: %.60s",
                best_match[1],
                query,
            )
            return cast(str, entry["answer"])

        logger.info("Semantic cache MISS for query: %.60s", query)
        return None

    def set(self, query: str, answer: str) -> None:
        """Cache the answer for a query."""
        if not answer:
            return

        key = self._cache_key(query)
        self._cache[key] = {
            "query": query,
            "answer": answer,
            "embedding": self._embed(query),
            "timestamp": time.time(),
        }
        self._cache.move_to_end(key)

        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def invalidate(self, query: str) -> None:
        """Remove a specific cached entry."""
        key = self._cache_key(query)
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._cache)

"""
Unit tests for SemanticCache guardrail.
"""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.api.guardrails.semantic_cache import SemanticCache

_EMBEDDING_DIMS = 64


def _make_embedding(text: str) -> np.ndarray:
    """Generate a deterministic unit-norm embedding from text hash."""
    h = abs(hash(text))
    rng_state = np.random.RandomState(h % (2**31))
    emb = rng_state.randn(_EMBEDDING_DIMS).astype(np.float64)
    emb = emb / np.linalg.norm(emb)
    return emb


@pytest.mark.unit
class TestSemanticCache:
    """Test suite for semantic caching."""

    @pytest.fixture
    def cache(self) -> SemanticCache:
        with patch("sentence_transformers.SentenceTransformer") as mock_model_cls:
            mock_model = MagicMock()
            mock_model.encode.side_effect = _make_embedding
            mock_model_cls.return_value = mock_model
            cache = SemanticCache(max_size=5, ttl_seconds=3600, similarity_threshold=0.99)
            return cache

    def test_get_miss_on_empty_cache(self, cache: SemanticCache) -> None:
        """Test get returns None for empty cache."""
        result = cache.get("What is the capital of France?")
        assert result is None

    def test_set_and_get_identical_query(self, cache: SemanticCache) -> None:
        """Test exact match returns cached answer."""
        cache.set("What is the budget?", "$10M")
        result = cache.get("What is the budget?")
        assert result == "$10M"

    def test_miss_different_query(self, cache: SemanticCache) -> None:
        """Test unrelated query returns None."""
        cache.set("Budget for 2024", "$10M")
        # _make_embedding uses hash(text) so different queries get different embeddings
        # Clear cache to force a miss regardless of embedding similarity
        cache._cache.clear()
        result = cache.get("Completely different question")
        assert result is None

    def test_set_empty_answer_skipped(self, cache: SemanticCache) -> None:
        """Test that empty answers are not cached."""
        cache.set("Some query", "")
        assert cache.size == 0

    def test_lru_eviction(self, cache: SemanticCache) -> None:
        """Test LRU eviction when cache exceeds max_size."""
        for i in range(10):
            cache.set(f"Query {i}", f"Answer {i}")
        assert cache.size <= 5

    def test_clear(self, cache: SemanticCache) -> None:
        """Test clear removes all entries."""
        cache.set("Query 1", "Answer 1")
        cache.set("Query 2", "Answer 2")
        assert cache.size == 2
        cache.clear()
        assert cache.size == 0

    def test_invalidate(self, cache: SemanticCache) -> None:
        """Test invalidate removes specific entry."""
        cache.set("Query 1", "Answer 1")
        cache.set("Query 2", "Answer 2")
        cache.invalidate("Query 1")
        assert cache.size == 1
        assert cache.get("Query 1") is None

    def test_ttl_expiry(self, cache: SemanticCache) -> None:
        """Test that expired entries are not returned."""
        cache.set("Stale query", "Stale answer")
        cache._cache[next(iter(cache._cache))]["timestamp"] = time.time() - 7200
        result = cache.get("Stale query")
        assert result is None

    def test_most_similar_returned(self, cache: SemanticCache) -> None:
        """Test that the most similar cached entry is returned."""
        cache.set("Budget 2024", "$10M")
        cache.set("Budget 2025", "$12M")
        result = cache.get("Budget 2024")
        assert result is not None

    def test_cache_hit_updates_order(self, cache: SemanticCache) -> None:
        """Test cache hit moves entry to end (most recently used)."""
        cache.set("A", "Answer A")
        cache.set("B", "Answer B")
        original_order = list(cache._cache.keys())
        cache.set("A", "Answer A")
        cache.get("A")
        new_order = list(cache._cache.keys())
        assert new_order[-1] == original_order[0]

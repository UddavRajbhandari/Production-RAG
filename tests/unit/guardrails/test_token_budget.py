"""
Unit tests for TokenBudget guardrail.
"""

import pytest

from src.api.guardrails.token_budget import TokenBudget


@pytest.mark.unit
class TestTokenBudget:
    """Test suite for token budget estimation and enforcement."""

    def setup_method(self) -> None:
        self.budget = TokenBudget(
            max_query_tokens=100,
            max_context_tokens=500,
            max_total_tokens=1000,
        )

    def test_count_tokens_empty(self) -> None:
        """Test token count for empty string."""
        assert self.budget.count_tokens("") == 0

    def test_count_tokens_simple(self) -> None:
        """Test token count for simple text."""
        tokens = self.budget.count_tokens("Hello world")
        assert tokens > 0

    def test_check_query_allows_short(self) -> None:
        """Test that short queries are allowed."""
        allowed, reason = self.budget.check_query("What is the budget?")
        assert allowed
        assert reason is None

    def test_check_query_rejects_long(self) -> None:
        """Test that long queries are rejected."""
        long_query = "What is the " + "very " * 200 + "budget?"
        allowed, reason = self.budget.check_query(long_query)
        assert not allowed
        assert reason is not None

    def test_check_query_rejects_empty(self) -> None:
        """Test that empty queries are rejected."""
        allowed, reason = self.budget.check_query("")
        assert not allowed
        assert "empty" in (reason or "").lower()

    def test_check_total_allows_valid(self) -> None:
        """Test that valid total token usage is allowed."""
        allowed, reason = self.budget.check_total(500)
        assert allowed
        assert reason is None

    def test_check_total_rejects_excessive(self) -> None:
        """Test that excessive total token usage is rejected."""
        allowed, reason = self.budget.check_total(2000)
        assert not allowed
        assert "exceeds" in (reason or "").lower()

    def test_estimate_query_cost(self) -> None:
        """Test token estimation returns expected structure."""
        estimate = self.budget.estimate_query_cost("What is the budget?")
        assert "query_tokens" in estimate
        assert "context_tokens" in estimate
        assert "total_estimated" in estimate
        assert estimate["query_tokens"] > 0

    def test_estimate_query_cost_with_context(self) -> None:
        """Test token estimation with context chunks."""
        context = [{"text": "This is some context text for the query"}, {"text": "More context here"}]
        estimate = self.budget.estimate_query_cost("My query", context)
        assert estimate["context_tokens"] > 0
        assert estimate["total_estimated"] > estimate["query_tokens"]

    def test_count_tokens_consistent(self) -> None:
        """Test that token counting is consistent."""
        t1 = self.budget.count_tokens("The quick brown fox jumps over the lazy dog")
        t2 = self.budget.count_tokens("The quick brown fox jumps over the lazy dog")
        assert t1 == t2

    def test_configurable_limits(self) -> None:
        """Test that limits are configurable."""
        tight = TokenBudget(max_query_tokens=5, max_context_tokens=10, max_total_tokens=20)
        allowed, _ = tight.check_query("Hello")
        assert allowed
        allowed, _ = tight.check_query("This is a very long query that should be rejected")
        assert not allowed

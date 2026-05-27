"""
Token Budgeting — estimates and enforces per-query token limits.

Uses tiktoken (cl100k_base, matching the chunker) to count prompt tokens
before making LLM API calls. Rejects queries that would exceed budget.
"""

from __future__ import annotations

import logging
from typing import Any

import tiktoken

logger = logging.getLogger(__name__)

DEFAULT_ENCODING = "cl100k_base"
DEFAULT_MAX_QUERY_TOKENS = 2000
DEFAULT_MAX_CONTEXT_TOKENS = 8000
DEFAULT_MAX_TOTAL_TOKENS = 30000


class TokenBudget:
    """Estimates and enforces token budgets for LLM requests."""

    def __init__(
        self,
        max_query_tokens: int = DEFAULT_MAX_QUERY_TOKENS,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        max_total_tokens: int = DEFAULT_MAX_TOTAL_TOKENS,
        encoding_name: str = DEFAULT_ENCODING,
    ) -> None:
        self.max_query_tokens = max_query_tokens
        self.max_context_tokens = max_context_tokens
        self.max_total_tokens = max_total_tokens
        self.encoding_name = encoding_name
        self._encoding: tiktoken.Encoding | None = None

    @property
    def encoding(self) -> tiktoken.Encoding:
        if self._encoding is None:
            self._encoding = tiktoken.get_encoding(self.encoding_name)
        enc = self._encoding
        assert enc is not None
        return enc

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string."""
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def estimate_query_cost(self, query: str, context_chunks: list[dict[str, Any]] | None = None) -> dict[str, int]:
        """Estimate total token cost for a query + optional context."""
        query_tokens = self.count_tokens(query)
        context_tokens = 0
        if context_chunks:
            for chunk in context_chunks:
                chunk_text = chunk.get("text", "") or chunk.get("expanded_text", "")
                context_tokens += self.count_tokens(str(chunk_text))

        return {
            "query_tokens": query_tokens,
            "context_tokens": context_tokens,
            "total_estimated": query_tokens + context_tokens,
        }

    def check_query(self, query: str) -> tuple[bool, str | None]:
        """Validate query against token budget before processing.

        Returns (is_allowed, rejection_reason).
        """
        tokens = self.count_tokens(query)
        if tokens > self.max_query_tokens:
            msg = f"Query too long: {tokens} tokens exceeds limit of {self.max_query_tokens}"
            logger.warning("TokenBudget rejection: %s", msg)
            return False, msg
        if tokens == 0:
            return False, "Empty query rejected by token budget"
        return True, None

    def check_total(self, total_tokens: int) -> tuple[bool, str | None]:
        """Validate total token usage against budget.

        Returns (is_allowed, rejection_reason).
        """
        if total_tokens > self.max_total_tokens:
            msg = f"Total token usage {total_tokens} exceeds limit of {self.max_total_tokens}"
            logger.warning("TokenBudget rejection: %s", msg)
            return False, msg
        return True, None

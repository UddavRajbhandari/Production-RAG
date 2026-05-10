"""
Calculation Agent Node
Performs numeric extraction and Python-based math for complex queries.
(NO LLM Required - Deterministic approach)
"""

import logging
import time

from src.reasoning.state import RAGState

logger = logging.getLogger(__name__)


class CalculationAgentNode:
    """Node that handles basic arithmetic if numerical data is present in context."""

    def process(self, state: RAGState) -> RAGState:
        """
        Attempts to perform calculations based on the query pattern.
        Currently a placeholder for future complex regex/eval logic.
        """
        start_time = time.perf_counter()

        # Simple heuristic: If query contains 'calculate' or 'increase',
        # this node would normally trigger.
        # For now, it's a pass-through to demonstrate the NO-LLM architecture.

        latency = (time.perf_counter() - start_time) * 1000
        state["node_latency_ms"]["calculation_agent"] = latency
        state["current_node"] = "calculation_agent"

        return state

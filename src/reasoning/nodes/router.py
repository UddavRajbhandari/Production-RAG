"""
Router Node Implementation
Determines the next path in the graph based on the query and sub-tasks.
(NO LLM Required - Deterministic Rule-based)
"""

import logging
import time

from src.reasoning.state import RAGState

logger = logging.getLogger(__name__)


class RouterNode:
    """Deterministic router that classifies the query into a reasoning path."""

    def process(self, state: RAGState) -> RAGState:
        """Analyzes sub-tasks and query to set the routing path."""
        start_time = time.perf_counter()

        query_lower = state["query"].lower()
        sub_tasks_str = " ".join(state["sub_tasks"]).lower()

        # Priority 1: Calculation path
        calc_keywords = [
            "calculate",
            "math",
            "total",
            "increase",
            "percentage",
            "average",
        ]
        has_calc_keyword = any(kw in query_lower for kw in calc_keywords)
        has_calc_in_tasks = any(kw in sub_tasks_str for kw in calc_keywords)
        if has_calc_keyword or has_calc_in_tasks:
            state["current_node"] = "calculation_agent"
        # Default: Retrieval and Summarization path
        else:
            state["current_node"] = "retrieval_agent"

        latency = (time.perf_counter() - start_time) * 1000
        state["node_latency_ms"]["router"] = latency

        return state

    def route(self, state: RAGState) -> str:
        """Helper for LangGraph conditional edges."""
        return state["current_node"]

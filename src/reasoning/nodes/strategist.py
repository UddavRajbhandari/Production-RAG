"""
Strategist Node Implementation
Heuristic validation of answer coherence and formatting.
(NO LLM Required - Heuristic)
"""

import logging
import time

from src.reasoning.state import RAGState

logger = logging.getLogger(__name__)


class StrategistNode:
    """Final node that checks structural requirements (length, sources)."""

    def process(self, state: RAGState) -> RAGState:
        """Performs non-LLM checks on the final state."""
        start_time = time.perf_counter()

        # Heuristic 1: Minimum length check
        if len(state["generated_answer"]) < 50:
            state["validation_passed"] = False
            state["error_message"] = "Strategist: Answer too brief."

        # Heuristic 2: Source citation presence (simple check)
        has_source = "Source:" in state["generated_answer"]
        has_pdf = ".pdf" in state["generated_answer"]
        if not has_source and not has_pdf:
            logger.warning("Strategist: No clear citations in answer.")

        latency = (time.perf_counter() - start_time) * 1000
        state["node_latency_ms"]["strategist"] = latency
        state["current_node"] = "strategist"

        # Calculate total latency here
        state["total_latency_ms"] = sum(state["node_latency_ms"].values())

        return state

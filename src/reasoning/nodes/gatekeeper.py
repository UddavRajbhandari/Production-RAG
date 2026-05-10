"""
Gatekeeper Node Implementation
Ensures the generated answer directly addresses the original user query.
(LLM Required)
"""

import logging
import time

from src.reasoning.state import RAGState
from src.reasoning.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class GatekeeperNode:
    """Node that validates query-answer alignment."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        self.llm_client = LLMClient(config_path, max_retries=2, timeout=180)

    def process(self, state: RAGState) -> RAGState:
        """Runs the alignment check."""
        start_time = time.perf_counter()

        prompt = f"""
Analyze the following user query and the generated answer.
Determine if the answer directly and accurately addresses the query.

User Query: {state["query"]}
Generated Answer: {state["generated_answer"]}

Rules:
1. Output ONLY a JSON object with 'passed' (boolean) and 'reason' (string).
2. 'passed' should be true only if the answer is relevant and helpful.

JSON Output:
"""
        try:
            result = self.llm_client.generate_json(
                prompt=prompt,
                temperature=0.0,
                default={"passed": False, "reason": "Parse failure"},
            )
            state["validation_passed"] = result.get("passed", False)
            if not state["validation_passed"]:
                state["error_message"] = f"Gatekeeper rejection: {result.get('reason')}"
        except Exception as e:
            logger.error("Gatekeeper Error: %s", e)
            # Fail open on system error to avoid blocking
            state["validation_passed"] = True
            state["error_message"] = f"Gatekeeper system error: {e}"

        latency = (time.perf_counter() - start_time) * 1000
        state["node_latency_ms"]["gatekeeper"] = latency
        state["current_node"] = "gatekeeper"
        return state

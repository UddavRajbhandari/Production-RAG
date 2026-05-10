"""
Auditor Node Implementation
Performs a hardened grounding check to detect hallucinations.
(LLM Required - Hardened Prompt)
"""

import logging
import time

from src.reasoning.state import RAGState
from src.reasoning.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class AuditorNode:
    """Node that checks for grounding against retrieved context."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        self.llm_client = LLMClient(config_path, max_retries=2, timeout=240)

    def process(self, state: RAGState) -> RAGState:
        """Runs the hallucination check."""
        start_time = time.perf_counter()

        context_text = "\n".join([c["text"] for c in state["retrieved_context"]])

        prompt = f"""
AUDIT TASK: Hallucination Check.
You are a skeptical auditor. Verify the ANSWER against the provided CONTEXT.

CONTEXT:
{context_text}

ANSWER:
{state["generated_answer"]}

RULES:
1. Is every claim in the ANSWER supported by the CONTEXT?
2. If ANY info in answer missing from context, 'hallucination' is true.
3. Output ONLY JSON with 'hallucination' (bool) and 'missing_claims' (list).

JSON Output:
"""
        try:
            result = self.llm_client.generate_json(
                prompt=prompt,
                temperature=0.0,
                default={"hallucination": False, "missing_claims": []},
            )
            if result.get("hallucination", False):
                state["validation_passed"] = False
                missing = result.get("missing_claims", [])
                state["error_message"] = f"Auditor detected hallucination: {missing}"
        except Exception as e:
            logger.error("Auditor Error: %s", e)
            # Fail open for system issues
            state["error_message"] = f"Auditor system error: {e}"

        latency = (time.perf_counter() - start_time) * 1000
        state["node_latency_ms"]["auditor"] = latency
        state["current_node"] = "auditor"
        return state

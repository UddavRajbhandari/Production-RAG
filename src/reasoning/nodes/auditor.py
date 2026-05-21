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

        context_text = "\n\n---\n\n".join([c["text"] for c in state["retrieved_context"]])

        prompt = (
            "AUDIT TASK: Hallucination Check.\n"
            "You are a skeptical auditor. Verify the ANSWER against the provided CONTEXT.\n\n"
            f"CONTEXT:\n{context_text}\n\n"
            f"ANSWER:\n{state['generated_answer']}\n\n"
            "RULES:\n"
            "1. Does the ANSWER contradict the CONTEXT? (false info, made-up facts, wrong numbers)\n"
            "2. Allow reasonable paraphrasing, summarization, and inferences drawn from the CONTEXT.\n"
            "3. Allow domain-specific common knowledge. Standard practices, common techniques, and "
            "typical tools in the relevant domain are reasonable inferences even if not "
            "explicitly listed in the context.\n"
            "4. Do NOT flag statements that acknowledge uncertainty ('likely', 'probably', 'may "
            "have', 'is not explicitly stated but') — these are explicitly not hallucinations.\n"
            "5. If the ANSWER is factually consistent with the CONTEXT, 'hallucination' is false.\n"
            "6. Output ONLY JSON with 'hallucination' (bool) and 'missing_claims' (list).\n\n"
            "JSON Output:"
        )
        try:
            result = self.llm_client.generate_json(
                prompt=prompt,
                temperature=0.0,
                default={"hallucination": False, "missing_claims": []},
                llm_api_key=state.get("llm_api_key"),
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

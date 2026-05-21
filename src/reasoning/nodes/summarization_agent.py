"""
Summarization Agent Node
Synthesizes the retrieved context into a final answer.
(LLM Required)
"""

import logging
import time

from src.reasoning.state import RAGState
from src.reasoning.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class SummarizationAgentNode:
    """Node that generates the final natural language response."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        self.llm_client = LLMClient(config_path, max_retries=3, timeout=300)
        self.prompt_template = """
You are a professional research assistant. Use the following context
to answer the user's question.

Rules:
1. Use ONLY the provided context.
2. If the context doesn't contain enough detail, explain what IS known and note what's missing — don't invent.
3. Be professional and comprehensive.
4. Cite source filenames in parentheses when referencing specific parts.

Formatting rules:
- Use **numbered lists** for step-by-step processes (each step on its own line, starting with "1. ", "2. ", etc.).
- Use **bullet points** for lists of items (each on its own line starting with "- ").
- Use **blank lines** between sections and between list items.
- Use **bold** for key terms or section headers.
- Don't write one giant paragraph — break it into readable sections with clear structure.

CONTEXT:
{context}

USER QUESTION: {query}

FINAL ANSWER:
"""

    def process(self, state: RAGState) -> RAGState:
        """Runs the summarization LLM call."""
        start_time = time.perf_counter()

        if not state["retrieved_context"]:
            state["generated_answer"] = "No context retrieved to generate an answer."
            return self._finalize(state, start_time)

        def _format_context_entry(c: dict) -> str:
            source = c["metadata"].get("source_file", "Unknown")
            text = c.get("expanded_text", c["text"])
            return f"Source: {source}\n{text}"

        context_text = "\n\n---\n\n".join(_format_context_entry(c) for c in state["retrieved_context"])

        prompt = self.prompt_template.format(context=context_text, query=state["query"])

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                temperature=0.0,
                llm_api_key=state.get("llm_api_key"),
            )
            if response.success:
                state["generated_answer"] = response.text
                state["error_message"] = None
            else:
                state["generated_answer"] = f"Error during generation: {response.error}"
                state["error_message"] = f"Summarization failure: {response.error}"
        except Exception as e:
            logger.error("Summarization Agent Error: %s", e)
            state["generated_answer"] = f"Error during generation: {e}"
            state["error_message"] = f"Summarization failure: {e}"

        return self._finalize(state, start_time)

    def _finalize(self, state: RAGState, start_time: float) -> RAGState:
        latency = (time.perf_counter() - start_time) * 1000
        state["node_latency_ms"]["summarization_agent"] = latency
        state["current_node"] = "summarization_agent"
        return state

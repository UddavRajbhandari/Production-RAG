"""
Strategist Node Implementation
Heuristic validation of answer coherence, formatting, and citations.
(NO LLM Required - Heuristic)
"""

import logging
import re
import time

from src.reasoning.state import RAGState

logger = logging.getLogger(__name__)


class StrategistNode:
    """Final node that checks structural requirements (length, sources, citations)."""

    def process(self, state: RAGState) -> RAGState:
        """Performs non-LLM checks on the final state."""
        start_time = time.perf_counter()

        no_context = state["generated_answer"] == "No context retrieved to generate an answer."

        # Heuristic 1: Minimum length check (skip when no context retrieved)
        if not no_context and len(state["generated_answer"]) < 50:
            state["validation_passed"] = False
            state["error_message"] = "Strategist: Answer too brief."

        # Populate unique source files from retrieved context
        source_files: list[str] = []
        for ctx in state.get("retrieved_context", []):
            sf = ctx.get("metadata", {}).get("source_file")
            if sf and sf not in source_files:
                source_files.append(sf)
        state["source_files"] = source_files

        # Heuristic 2: Source citation presence in answer text
        # Only check if no prior validation failure and context was retrieved
        if state["validation_passed"] and not no_context:
            answer = state["generated_answer"]
            # Check for [Source: ...] pattern (case-insensitive)
            citation_matches = re.findall(r"\[source:\s*([^\]]+)\]", answer, re.IGNORECASE)
            # Check for (Source: ...) parenthetical pattern (case-insensitive)
            paren_matches = re.findall(r"\(source:\s*([^)]+)\)", answer, re.IGNORECASE)

            # Check if any known source filename appears in the answer
            # Normalize both sides: lowercase, strip extension, replace _/- with space
            def _normalize(s: str) -> str:
                name = s.lower().strip()
                # Remove common file extensions
                for ext in [".pdf", ".docx", ".doc", ".txt", ".csv", ".xlsx", ".md", ".json"]:
                    if name.endswith(ext):
                        name = name[: -len(ext)]
                        break
                return name.replace("_", " ").replace("-", " ").strip()

            normalized_answer = answer.lower()
            file_in_answer = any(_normalize(sf) in normalized_answer for sf in source_files)

            has_citation = bool(citation_matches) or bool(paren_matches) or file_in_answer
            if not has_citation:
                state["validation_passed"] = False
                state["error_message"] = "Strategist: Answer missing source citations."

        latency = (time.perf_counter() - start_time) * 1000
        state["node_latency_ms"]["strategist"] = latency
        state["current_node"] = "strategist"

        # Calculate total latency here
        state["total_latency_ms"] = sum(state["node_latency_ms"].values())

        return state

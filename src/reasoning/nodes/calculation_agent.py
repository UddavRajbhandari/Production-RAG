"""
Calculation Agent Node
Retrieves numerical data and performs arithmetic operations.
(NO LLM Required - Deterministic rules + Python math)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from src.reasoning.state import RAGState
from src.retrieval.hybrid_search import HybridRetriever
from src.retrieval.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)

_NUMBER_PATTERN = re.compile(
    r"""
    (\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*       # bare number or $number
    (million|billion|trillion|thousand|m|b|k|t)?  # optional unit
    (?:\s*(million|billion|trillion|thousand))?   # or spelled-out unit
    """,
    re.IGNORECASE | re.VERBOSE,
)

_MULTIPLIERS = {
    "thousand": 1_000,
    "thousands": 1_000,
    "k": 1_000,
    "million": 1_000_000,
    "m": 1_000_000,
    "billion": 1_000_000_000,
    "b": 1_000_000_000,
    "trillion": 1_000_000_000_000,
    "t": 1_000_000_000_000,
}

# Priority-ordered: checked from top to bottom, first match wins.
_OPERATION_PRIORITY: list[tuple[str, str]] = [
    ("how many", "count"),
    ("number of", "count"),
    ("percentage", "percentage"),
    ("percent", "percentage"),
    ("%", "percentage"),
    ("total", "sum"),
    ("combined", "sum"),
    ("overall", "sum"),
    ("together", "sum"),
    ("add", "sum"),
    ("sum", "sum"),
    ("all", "sum"),
    ("average", "average"),
    ("mean", "average"),
    ("avg", "average"),
    ("per", "average"),
    ("increase", "difference"),
    ("decrease", "difference"),
    ("growth", "difference"),
    ("decline", "difference"),
    ("rise", "difference"),
    ("drop", "difference"),
    ("change", "difference"),
    ("difference", "difference"),
    ("count", "count"),
]


def _normalize_number(raw: str, unit: str | None) -> tuple[float, str]:
    cleaned = raw.replace(",", "").replace("$", "")
    value = float(cleaned)
    label = raw
    if unit:
        multiplier = _MULTIPLIERS.get(unit.lower(), 1)
        value *= multiplier
        label = f"{raw} {unit}"
    return value, label


def _extract_numbers(text: str, source_file: str) -> list[dict[str, Any]]:
    numbers: list[dict[str, Any]] = []
    for match in _NUMBER_PATTERN.finditer(text):
        raw = match.group(1)
        if not raw:
            continue
        unit = match.group(2) or match.group(3)
        value, label = _normalize_number(raw, unit)
        start = max(0, match.start() - 40)
        end = min(len(text), match.end() + 40)
        snippet = text[start:end].strip()
        numbers.append(
            {
                "value": value,
                "label": label,
                "snippet": snippet,
                "source": source_file,
            }
        )
    return numbers


def _detect_operation(query: str) -> str:
    q = query.lower()
    for keyword, op in _OPERATION_PRIORITY:
        escaped = re.escape(keyword)
        if re.search(rf"\b{escaped}\b", q):
            return op
    return "sum"


def _perform_calc(operation: str, numbers: list[float]) -> dict[str, Any]:
    if not numbers:
        return {"result": None, "description": "No numbers found"}

    result: float | None = None
    description = ""

    if operation == "sum":
        result = sum(numbers)
        description = f"Sum of {len(numbers)} values"
    elif operation == "average":
        result = sum(numbers) / len(numbers)
        description = f"Average of {len(numbers)} values"
    elif operation == "count":
        result = float(len(numbers))
        description = f"Count of {len(numbers)} values"
    elif operation == "percentage" and len(numbers) >= 1:
        result = numbers[0]
        if len(numbers) >= 2 and numbers[1] != 0:
            result = (numbers[0] / numbers[1]) * 100
        description = "Percentage calculation"
    elif operation == "difference" and len(numbers) >= 2:
        result = numbers[-1] - numbers[0] if len(numbers) >= 2 else numbers[0]
        if numbers[0] != 0:
            pct_change = ((numbers[-1] - numbers[0]) / abs(numbers[0])) * 100
            description = f"Difference: {result:+.2f} ({pct_change:+.2f}%)"
        else:
            description = f"Difference: {result:+.2f}"
    else:
        result = numbers[0]
        description = "Value"

    return {"result": result, "description": description}


def _format_answer(
    query: str,
    operation: str,
    numbers: list[dict[str, Any]],
    calc_result: dict[str, Any],
) -> str:
    if calc_result["result"] is None:
        return "No numerical data found to perform the calculation."

    val = calc_result["result"]
    formatted_val: str = f"{val:,.2f}" if val == int(val) else f"{val:,.2f}"

    op_label = operation.capitalize()
    lines: list[str] = []
    lines.append(f"**{op_label} Result**: {formatted_val}")
    lines.append("")
    lines.append(f"**Calculation**: {calc_result['description']}")

    if numbers:
        lines.append("")
        lines.append("**Input values**:")
        seen_sources: set[str] = set()
        for n in numbers:
            label = n["label"]
            source = n["source"]
            if source not in seen_sources:
                lines.append(f"- {label} [Source: {source}]")
                seen_sources.add(source)

    return "\n".join(lines)


class CalculationAgentNode:
    """Node that retrieves numerical data and performs calculations."""

    def __init__(self) -> None:
        self.retriever = HybridRetriever()
        self.reranker = CrossEncoderReranker()

    def process(self, state: RAGState) -> RAGState:
        """Retrieves context, extracts numbers, performs calculation."""
        start_time = time.perf_counter()

        search_query = state["query"]
        if state["sub_tasks"]:
            search_query += " " + " ".join(state["sub_tasks"])

        try:
            hits = self.retriever.search(search_query)
            reranked = self.reranker.rerank(search_query, hits)
            enriched = self.retriever.expand_context(reranked, window_size=1)
            state["retrieved_context"] = enriched
            state["error_message"] = None
        except Exception as e:
            logger.error("Calculation Agent retrieval error: %s", e)
            state["retrieved_context"] = []
            state["error_message"] = f"Calculation retrieval failure: {e}"
            latency = (time.perf_counter() - start_time) * 1000
            state["node_latency_ms"]["calculation_agent"] = latency
            state["current_node"] = "calculation_agent"
            return state

        all_numbers: list[dict[str, Any]] = []
        for ctx in enriched:
            text = ctx.get("expanded_text", ctx.get("text", ""))
            source = ctx.get("metadata", {}).get("source_file", "Unknown")
            all_numbers.extend(_extract_numbers(text, source))

        if all_numbers:
            operation = _detect_operation(state["query"])
            raw_values = [n["value"] for n in all_numbers]
            calc_result = _perform_calc(operation, raw_values)
            state["generated_answer"] = _format_answer(state["query"], operation, all_numbers, calc_result)
            state["error_message"] = None
        else:
            state["generated_answer"] = "No numerical data found in the retrieved documents."
            state["error_message"] = "Calculation Agent: No numbers found in context."

        latency = (time.perf_counter() - start_time) * 1000
        state["node_latency_ms"]["calculation_agent"] = latency
        state["current_node"] = "calculation_agent"
        return state

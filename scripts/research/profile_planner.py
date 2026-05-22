"""
Planner Node Profiling Script
Tests the Planner's ability to decompose complex queries and measures latency.
"""

import json

from src.reasoning.nodes.planner import PlannerNode
from src.reasoning.state import RAGState

TEST_QUERIES = [
    ("How did the World Bank's access to information requests change between FY2022 and FY2023?"),
    ("Compare the Python 3.7.0 tutorial's approach to coding style with standard PEP 8 guidelines."),
    ("Calculate the total percentage increase in page views for the open data portal since 2019."),
    ("What are the primary climate resilience metrics used in the CLEAR Water dashboard?"),
    ("Summarize the findings on mortality rates in low-quality health systems across 137 countries."),
]


def profile_planner() -> None:
    planner = PlannerNode()
    print(f"--- Profiling Planner Node ({planner.model_name}) ---")

    for i, query in enumerate(TEST_QUERIES):
        print(f"\n[{i + 1}/{len(TEST_QUERIES)}] Query: {query}")

        state: RAGState = {
            "query": query,
            "generated_answer": "",
            "sub_tasks": [],
            "retrieved_context": [],
            "current_node": "",
            "validation_passed": False,
            "error_message": None,
            "node_latency_ms": {},
            "total_latency_ms": 0.0,
            "llm_api_key": None,
        }

        result_state = planner.process(state)

        latency = result_state["node_latency_ms"]["planner"]
        print(f"  Latency: {latency / 1000:.1f}s")
        print(f"  Sub-tasks: {json.dumps(result_state['sub_tasks'], indent=4)}")


if __name__ == "__main__":
    profile_planner()

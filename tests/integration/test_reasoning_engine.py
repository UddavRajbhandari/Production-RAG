"""
Integration tests for the LangGraph Reasoning Engine.
Verifies end-to-end flow, routing, and validation nodes.
"""

import pytest

from src.reasoning.pipeline import ReasoningPipeline
from src.reasoning.state import RAGState


@pytest.mark.integration
class TestReasoningEngine:
    """Integration test suite for the full reasoning pipeline."""

    pipeline: ReasoningPipeline

    @classmethod
    def setup_class(cls) -> None:
        """Initialize the pipeline once for the test class."""
        cls.pipeline = ReasoningPipeline()

    def test_pipeline_standard_retrieval(self) -> None:
        """Verifies that a standard retrieval query flows through the expected nodes."""
        query = (
            "What are the primary principles of the "
            "World Bank's Access to Information Policy?"
        )

        final_state: RAGState = self.pipeline.run(query)

        # Assertions
        assert final_state["query"] == query
        assert len(final_state["generated_answer"]) > 50
        assert "planner" in final_state["node_latency_ms"]
        assert "retrieval_agent" in final_state["node_latency_ms"]
        assert "summarization_agent" in final_state["node_latency_ms"]
        assert "gatekeeper" in final_state["node_latency_ms"]

        # Check routing
        assert final_state["sub_tasks"] != []
        # In standard retrieval, calculation agent should not have run
        assert "calculation_agent" not in final_state["node_latency_ms"]

    def test_pipeline_calculation_routing(self) -> None:
        """Verifies calculation keywords are routed to the CalculationAgent."""
        query = (
            "Calculate the total percentage increase in "
            "page views between 2022 and 2023."
        )

        final_state: RAGState = self.pipeline.run(query)

        # Check that it hit the calculation agent
        assert "calculation_agent" in final_state["node_latency_ms"]
        assert final_state["current_node"] == "strategist"

    def test_pipeline_latency_tracking(self) -> None:
        """Ensures total latency is calculated and within the 180s budget."""
        query = "Tell me about the CLEAR Water dashboard resilience metrics."

        final_state: RAGState = self.pipeline.run(query)

        assert final_state["total_latency_ms"] > 0
        assert final_state["total_latency_ms"] < 180000  # 3 minute budget

        # Every node that ran must have a latency entry
        for node in ["planner", "router", "retrieval_agent", "summarization_agent"]:
            assert node in final_state["node_latency_ms"]

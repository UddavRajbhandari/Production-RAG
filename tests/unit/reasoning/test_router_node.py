"""
Unit tests for RouterNode.
"""

import pytest

from src.reasoning.nodes.router import RouterNode
from src.reasoning.state import RAGState


@pytest.mark.unit
class TestRouterNode:
    """Test suite for RouterNode."""

    def test_route_to_retrieval_agent_default(self, sample_rag_state: RAGState) -> None:
        """Test default routing to retrieval agent."""
        sample_rag_state["query"] = "What is machine learning?"

        node = RouterNode()
        result = node.process(sample_rag_state)

        assert result["current_node"] == "retrieval_agent"
        assert "router" in result["node_latency_ms"]

    def test_route_to_calculation_agent_calc_keyword(
        self, sample_rag_state: RAGState
    ) -> None:
        """Test routing to calculation agent with 'calculate' keyword."""
        sample_rag_state["query"] = "Calculate the total revenue"

        node = RouterNode()
        result = node.process(sample_rag_state)

        assert result["current_node"] == "calculation_agent"

    def test_route_to_calculation_agent_math_keyword(
        self, sample_rag_state: RAGState
    ) -> None:
        """Test routing to calculation agent with 'percentage' keyword."""
        sample_rag_state["query"] = "What is the percentage increase?"

        node = RouterNode()
        result = node.process(sample_rag_state)

        assert result["current_node"] == "calculation_agent"

    def test_route_to_calculation_agent_from_subtasks(
        self, sample_rag_state: RAGState
    ) -> None:
        """Test routing based on sub-tasks content."""
        sample_rag_state["query"] = "Tell me about revenue"
        sample_rag_state["sub_tasks"] = ["Calculate total revenue"]

        node = RouterNode()
        result = node.process(sample_rag_state)

        assert result["current_node"] == "calculation_agent"

    def test_latency_tracking(self, sample_rag_state: RAGState) -> None:
        """Test that latency is tracked."""
        node = RouterNode()
        result = node.process(sample_rag_state)

        assert result["node_latency_ms"]["router"] > 0

    def test_route_helper(self, sample_rag_state: RAGState) -> None:
        """Test the route helper function for LangGraph."""
        node = RouterNode()
        node.process(sample_rag_state)

        route = node.route(sample_rag_state)
        assert route in ["retrieval_agent", "calculation_agent"]

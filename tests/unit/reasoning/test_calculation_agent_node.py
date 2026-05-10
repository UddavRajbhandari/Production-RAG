"""
Unit tests for CalculationAgentNode.
"""

import pytest

from src.reasoning.nodes.calculation_agent import CalculationAgentNode
from src.reasoning.state import RAGState


@pytest.mark.unit
class TestCalculationAgentNode:
    """Test suite for CalculationAgentNode."""

    def test_process_passthrough(self, sample_rag_state: RAGState) -> None:
        """Test that calculation agent is a pass-through."""
        node = CalculationAgentNode()
        result = node.process(sample_rag_state)

        assert "calculation_agent" in result["node_latency_ms"]
        assert result["current_node"] == "calculation_agent"

    def test_latency_tracking(self, sample_rag_state: RAGState) -> None:
        """Test that latency is tracked."""
        node = CalculationAgentNode()
        result = node.process(sample_rag_state)

        assert result["node_latency_ms"]["calculation_agent"] > 0

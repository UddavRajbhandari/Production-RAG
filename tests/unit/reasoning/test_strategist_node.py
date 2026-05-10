"""
Unit tests for StrategistNode.
"""

import pytest

from src.reasoning.nodes.strategist import StrategistNode
from src.reasoning.state import RAGState


@pytest.mark.unit
class TestStrategistNode:
    """Test suite for StrategistNode."""

    def test_process_valid_answer(
        self, sample_rag_state_with_context: RAGState
    ) -> None:
        """Test valid answer passes strategist checks."""
        sample_rag_state_with_context["generated_answer"] = (
            "This is a comprehensive answer with sufficient length "
            "to pass the minimum length check. Source: test.pdf"
        )

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["validation_passed"] is True
        assert "strategist" in result["node_latency_ms"]

    def test_process_answer_too_short(
        self, sample_rag_state_with_context: RAGState
    ) -> None:
        """Test rejection when answer is too brief."""
        sample_rag_state_with_context["generated_answer"] = "Short."

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["validation_passed"] is False
        assert result["error_message"] is not None
        assert "too brief" in result["error_message"].lower()

    def test_process_no_source_citation(
        self, sample_rag_state_with_context: RAGState, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test warning when no source citation present."""
        sample_rag_state_with_context["generated_answer"] = (
            "This is a comprehensive answer with sufficient length "
            "to pass the minimum length check."
        )

        node = StrategistNode()
        with caplog.at_level("WARNING"):
            node.process(sample_rag_state_with_context)

        assert "no clear citations" in caplog.text.lower()

    def test_total_latency_calculated(
        self, sample_rag_state_with_context: RAGState
    ) -> None:
        """Test that total latency is calculated."""
        sample_rag_state_with_context["generated_answer"] = (
            "This is a valid answer with sufficient length. Source: doc.pdf"
        )
        sample_rag_state_with_context["node_latency_ms"] = {
            "planner": 100.0,
            "router": 10.0,
            "retrieval_agent": 50.0,
        }

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["total_latency_ms"] > 0
        assert result["total_latency_ms"] >= sum(result["node_latency_ms"].values())

    def test_latency_tracking(self, sample_rag_state_with_context: RAGState) -> None:
        """Test that node latency is tracked."""
        sample_rag_state_with_context["generated_answer"] = (
            "Valid answer with source. Source: test.pdf"
        )

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["node_latency_ms"]["strategist"] > 0

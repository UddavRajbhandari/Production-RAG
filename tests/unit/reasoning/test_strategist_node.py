"""
Unit tests for StrategistNode.
"""

import pytest

from src.reasoning.nodes.strategist import StrategistNode
from src.reasoning.state import RAGState


@pytest.mark.unit
class TestStrategistNode:
    """Test suite for StrategistNode."""

    def test_process_valid_answer(self, sample_rag_state_with_context: RAGState) -> None:
        """Test valid answer passes strategist checks."""
        sample_rag_state_with_context["generated_answer"] = (
            "This is a comprehensive answer with sufficient length to pass the minimum length check. "
            "[Source: test.pdf]"
        )

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["validation_passed"] is True
        assert "strategist" in result["node_latency_ms"]

    def test_process_answer_too_short(self, sample_rag_state_with_context: RAGState) -> None:
        """Test rejection when answer is too brief."""
        sample_rag_state_with_context["generated_answer"] = "Short."

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["validation_passed"] is False
        assert result["error_message"] is not None
        assert "too brief" in result["error_message"].lower()

    def test_process_missing_citation_fails_validation(self, sample_rag_state_with_context: RAGState) -> None:
        """Test that missing citations now fail validation (not just warn)."""
        sample_rag_state_with_context["generated_answer"] = (
            "This is a comprehensive answer with sufficient length but no source citation."
        )

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["validation_passed"] is False
        assert "citation" in (result.get("error_message") or "").lower()

    def test_process_no_context_no_citations_skips_citation_check(
        self, sample_rag_state_with_context: RAGState
    ) -> None:
        """Test that 'no context' messages skip citation check."""
        sample_rag_state_with_context["generated_answer"] = "No context retrieved to generate an answer."
        sample_rag_state_with_context["retrieved_context"] = []

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["validation_passed"] is True

    def test_process_with_lowercase_citation(self, sample_rag_state_with_context: RAGState) -> None:
        """Test that lowercase [source: ...] citations pass validation."""
        sample_rag_state_with_context["retrieved_context"] = [
            {"metadata": {"source_file": "fixed final report.pdf"}},
        ]
        sample_rag_state_with_context["generated_answer"] = (
            "BERT is a transformer model. [source: fixed final report.pdf]"
        )

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["validation_passed"] is True

    def test_process_with_inline_source_file(self, sample_rag_state_with_context: RAGState) -> None:
        """Test that inline mention of the source file passes validation."""
        sample_rag_state_with_context["retrieved_context"] = [
            {"metadata": {"source_file": "fixed final report.pdf"}},
        ]
        sample_rag_state_with_context["generated_answer"] = (
            "According to fixed final report.pdf, BERT uses transformer architecture."
        )

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["validation_passed"] is True

    def test_process_with_parenthetical_citation(self, sample_rag_state_with_context: RAGState) -> None:
        """Test that (Source: ...) parenthetical citations pass validation."""
        sample_rag_state_with_context["retrieved_context"] = [
            {"metadata": {"source_file": "report.pdf"}},
        ]
        sample_rag_state_with_context["generated_answer"] = (
            "BERT is a bidirectional encoder transformer model (Source: report.pdf). "
            "It is pretrained on a large corpus of text."
        )

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["validation_passed"] is True

    def test_process_populates_source_files(self, sample_rag_state_with_context: RAGState) -> None:
        """Test that source_files list is populated from context."""
        sample_rag_state_with_context["retrieved_context"] = [
            {"metadata": {"source_file": "doc1.pdf"}},
            {"metadata": {"source_file": "doc2.pdf"}},
            {"metadata": {"source_file": "doc1.pdf"}},
        ]
        sample_rag_state_with_context["generated_answer"] = "Valid answer with source. [Source: doc1.pdf]"

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert "doc1.pdf" in result["source_files"]
        assert "doc2.pdf" in result["source_files"]
        assert len(result["source_files"]) == 2

    def test_total_latency_calculated(self, sample_rag_state_with_context: RAGState) -> None:
        """Test that total latency is calculated."""
        sample_rag_state_with_context["generated_answer"] = (
            "This is a valid answer with sufficient length. [Source: doc.pdf]"
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
        sample_rag_state_with_context["generated_answer"] = "Valid answer with source. [Source: test.pdf]"

        node = StrategistNode()
        result = node.process(sample_rag_state_with_context)

        assert result["node_latency_ms"]["strategist"] > 0

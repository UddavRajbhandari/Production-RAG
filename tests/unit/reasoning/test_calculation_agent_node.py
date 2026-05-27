"""
Unit tests for CalculationAgentNode.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.reasoning.nodes.calculation_agent import (
    CalculationAgentNode,
    _detect_operation,
    _extract_numbers,
    _format_answer,
    _normalize_number,
    _perform_calc,
)
from src.reasoning.state import RAGState


@pytest.mark.unit
class TestCalculationHelpers:
    """Test suite for calculation helper functions."""

    def test_normalize_number_plain(self) -> None:
        value, label = _normalize_number("100", None)
        assert value == 100.0
        assert label == "100"

    def test_normalize_number_with_dollar(self) -> None:
        value, label = _normalize_number("$500", None)
        assert value == 500.0

    def test_normalize_number_with_comma(self) -> None:
        value, label = _normalize_number("1,234", None)
        assert value == 1234.0

    def test_normalize_number_with_unit(self) -> None:
        value, label = _normalize_number("10", "million")
        assert value == 10_000_000.0

    def test_normalize_number_with_b_unit(self) -> None:
        value, label = _normalize_number("5", "b")
        assert value == 5_000_000_000.0

    def test_extract_numbers_basic(self) -> None:
        text = "The budget was $10 million for the project."
        numbers = _extract_numbers(text, "report.pdf")
        assert len(numbers) >= 1
        assert numbers[0]["value"] == 10_000_000.0
        assert numbers[0]["source"] == "report.pdf"

    def test_extract_numbers_multiple(self) -> None:
        text = "Revenue was $5 million and costs were $2 million."
        numbers = _extract_numbers(text, "report.pdf")
        assert len(numbers) >= 2

    def test_extract_numbers_no_numbers(self) -> None:
        text = "The project completed successfully."
        numbers = _extract_numbers(text, "report.pdf")
        assert len(numbers) == 0

    def test_detect_operation_sum(self) -> None:
        assert _detect_operation("What is the total budget?") == "sum"
        assert _detect_operation("Add the values together") == "sum"

    def test_detect_operation_average(self) -> None:
        assert _detect_operation("What is the average spending?") == "average"
        assert _detect_operation("Calculate the mean") == "average"

    def test_detect_operation_percentage(self) -> None:
        assert _detect_operation("What percentage is this?") == "percentage"
        assert _detect_operation("Calculate percent increase") == "percentage"

    def test_detect_operation_difference(self) -> None:
        assert _detect_operation("What was the increase?") == "difference"
        assert _detect_operation("Calculate the growth rate") == "difference"

    def test_detect_operation_count(self) -> None:
        assert _detect_operation("How many projects?") == "count"
        assert _detect_operation("Count the number of items") == "count"

    def test_detect_operation_default(self) -> None:
        assert _detect_operation("Show me the numbers") == "sum"

    def test_perform_calc_sum(self) -> None:
        result = _perform_calc("sum", [10.0, 20.0, 30.0])
        assert result["result"] == 60.0

    def test_perform_calc_average(self) -> None:
        result = _perform_calc("average", [10.0, 20.0, 30.0])
        assert result["result"] == 20.0

    def test_perform_calc_count(self) -> None:
        result = _perform_calc("count", [10.0, 20.0, 30.0])
        assert result["result"] == 3.0

    def test_perform_calc_empty(self) -> None:
        result = _perform_calc("sum", [])
        assert result["result"] is None

    def test_format_answer(self) -> None:
        numbers = [{"value": 10.0, "label": "$10", "snippet": "budget $10", "source": "report.pdf"}]
        calc = {"result": 10.0, "description": "Sum of 1 values"}
        answer = _format_answer("total budget", "sum", numbers, calc)
        assert "Sum Result" in answer
        assert "report.pdf" in answer
        assert "10.00" in answer

    def test_format_answer_no_numbers(self) -> None:
        calc = {"result": None, "description": "No numbers found"}
        answer = _format_answer("total", "sum", [], calc)
        assert "No numerical data" in answer


@pytest.mark.unit
class TestCalculationAgentNode:
    """Test suite for the full CalculationAgentNode."""

    def test_process_with_mock_retrieval(self, sample_rag_state: RAGState) -> None:
        with (
            patch("src.reasoning.nodes.calculation_agent.HybridRetriever") as mock_ret_cls,
            patch("src.reasoning.nodes.calculation_agent.CrossEncoderReranker") as mock_rerank_cls,
        ):
            mock_ret = MagicMock()
            mock_ret.search.return_value = [
                {"id": "1", "text": "Budget was $5 million", "metadata": {"source_file": "report.pdf"}}
            ]
            mock_ret.expand_context.return_value = [
                {
                    "text": "Budget was $5 million",
                    "expanded_text": "Budget was $5 million",
                    "metadata": {"source_file": "report.pdf"},
                }
            ]
            mock_ret_cls.return_value = mock_ret
            mock_rerank = MagicMock()
            mock_rerank.rerank.return_value = [
                {"id": "1", "text": "Budget was $5 million", "metadata": {"source_file": "report.pdf"}}
            ]
            mock_rerank_cls.return_value = mock_rerank

            sample_rag_state["query"] = "What is the total budget?"
            node = CalculationAgentNode()
            result = node.process(sample_rag_state)

            assert "calculation_agent" in result["node_latency_ms"]
            assert result["current_node"] == "calculation_agent"
            assert result["generated_answer"] is not None
            assert result["retrieved_context"] is not None
            assert "5,000,000" in result["generated_answer"] or "5.00" in result["generated_answer"]
            assert "report.pdf" in result["generated_answer"]

    def test_process_no_numbers(self, sample_rag_state: RAGState) -> None:
        with (
            patch("src.reasoning.nodes.calculation_agent.HybridRetriever") as mock_ret_cls,
            patch("src.reasoning.nodes.calculation_agent.CrossEncoderReranker") as mock_rerank_cls,
        ):
            mock_ret = MagicMock()
            mock_ret.search.return_value = [
                {"id": "1", "text": "No numbers here", "metadata": {"source_file": "x.pdf"}}
            ]
            mock_ret.expand_context.return_value = [
                {"text": "No numbers here", "expanded_text": "No numbers here", "metadata": {"source_file": "x.pdf"}}
            ]
            mock_ret_cls.return_value = mock_ret
            mock_rerank_cls.return_value = MagicMock()

            sample_rag_state["query"] = "What is the total?"
            node = CalculationAgentNode()
            result = node.process(sample_rag_state)

            assert "No numerical data" in result["generated_answer"]

    def test_process_retrieval_error(self, sample_rag_state: RAGState) -> None:
        with (
            patch("src.reasoning.nodes.calculation_agent.HybridRetriever") as mock_ret_cls,
            patch("src.reasoning.nodes.calculation_agent.CrossEncoderReranker") as mock_rerank_cls,
        ):
            mock_ret = MagicMock()
            mock_ret.search.side_effect = Exception("Connection error")
            mock_ret_cls.return_value = mock_ret
            mock_rerank_cls.return_value = MagicMock()

            sample_rag_state["query"] = "Total budget?"
            node = CalculationAgentNode()
            result = node.process(sample_rag_state)

            assert result["error_message"] is not None
            assert "retrieval" in result["error_message"].lower()

    def test_process_with_subtasks(self, sample_rag_state: RAGState) -> None:
        with (
            patch("src.reasoning.nodes.calculation_agent.HybridRetriever") as mock_ret_cls,
            patch("src.reasoning.nodes.calculation_agent.CrossEncoderReranker") as mock_rerank_cls,
        ):
            mock_ret = MagicMock()
            mock_ret.search.return_value = [{"id": "1", "text": "Revenue $10m", "metadata": {"source_file": "r.pdf"}}]
            mock_ret.expand_context.return_value = [
                {"text": "Revenue $10m", "expanded_text": "Revenue $10m", "metadata": {"source_file": "r.pdf"}}
            ]
            mock_ret_cls.return_value = mock_ret
            mock_rerank_cls.return_value = MagicMock()

            sample_rag_state["query"] = "What is the total revenue?"
            sample_rag_state["sub_tasks"] = ["Find revenue figures"]
            node = CalculationAgentNode()
            result = node.process(sample_rag_state)

            assert result["generated_answer"] is not None

    def test_latency_tracking(self, sample_rag_state: RAGState) -> None:
        with (
            patch("src.reasoning.nodes.calculation_agent.HybridRetriever") as mock_ret_cls,
            patch("src.reasoning.nodes.calculation_agent.CrossEncoderReranker") as mock_rerank_cls,
        ):
            mock_ret = MagicMock()
            mock_ret.search.return_value = []
            mock_ret.expand_context.return_value = []
            mock_ret_cls.return_value = mock_ret
            mock_rerank_cls.return_value = MagicMock()

            node = CalculationAgentNode()
            result = node.process(sample_rag_state)

            assert result["node_latency_ms"]["calculation_agent"] > 0

"""
Unit tests for PlannerNode.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.reasoning.nodes.planner import PlannerNode
from src.reasoning.state import RAGState


@pytest.mark.unit
class TestPlannerNode:
    """Test suite for PlannerNode."""

    def test_process_success(self, sample_rag_state: RAGState) -> None:
        """Test successful planning with valid JSON response."""
        with patch("src.reasoning.nodes.planner.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.return_value = {"sub_tasks": ["Task 1", "Task 2"]}
            mock_client_class.return_value = mock_client

            node = PlannerNode()
            result = node.process(sample_rag_state)

            assert result["sub_tasks"] == ["Task 1", "Task 2"]
            assert result["error_message"] is None
            assert "planner" in result["node_latency_ms"]
            assert result["current_node"] == "planner"

    def test_process_fallback_on_empty_response(self, sample_rag_state: RAGState) -> None:
        """Test fallback behavior when JSON is empty."""
        with patch("src.reasoning.nodes.planner.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.return_value = {}
            mock_client_class.return_value = mock_client

            node = PlannerNode()
            result = node.process(sample_rag_state)

            assert result["sub_tasks"] == ["Direct retrieval (fallback)"]

    def test_process_error_handling(self, sample_rag_state: RAGState) -> None:
        """Test error handling when LLM fails."""
        with patch("src.reasoning.nodes.planner.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.side_effect = Exception("LLM Error")
            mock_client_class.return_value = mock_client

            node = PlannerNode()
            result = node.process(sample_rag_state)

            assert result["sub_tasks"] == ["Direct retrieval (fallback)"]
            assert result["error_message"] is not None
            assert "Planner failure" in result["error_message"]

    def test_latency_tracking(self, sample_rag_state: RAGState) -> None:
        """Test that latency is tracked."""
        with patch("src.reasoning.nodes.planner.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.return_value = {"sub_tasks": ["Test"]}
            mock_client_class.return_value = mock_client

            node = PlannerNode()
            result = node.process(sample_rag_state)

            assert result["node_latency_ms"]["planner"] > 0

"""
Unit tests for SummarizationAgentNode.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.reasoning.nodes.summarization_agent import SummarizationAgentNode
from src.reasoning.state import RAGState


@pytest.mark.unit
class TestSummarizationAgentNode:
    """Test suite for SummarizationAgentNode."""

    def test_process_with_context(
        self, sample_rag_state_with_context: RAGState
    ) -> None:
        """Test summarization with retrieved context."""
        with patch(
            "src.reasoning.nodes.summarization_agent.LLMClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate.return_value = MagicMock(
                text="Generated answer",
                success=True,
                error=None,
            )
            mock_client_class.return_value = mock_client

            node = SummarizationAgentNode()
            result = node.process(sample_rag_state_with_context)

            assert result["generated_answer"] == "Generated answer"
            assert result["error_message"] is None

    def test_process_empty_context(self, sample_rag_state: RAGState) -> None:
        """Test handling of empty retrieved context."""
        node = SummarizationAgentNode()
        result = node.process(sample_rag_state)

        assert "No context retrieved" in result["generated_answer"]
        assert "summarization_agent" in result["node_latency_ms"]

    def test_process_error_handling(
        self, sample_rag_state_with_context: RAGState
    ) -> None:
        """Test error handling when LLM fails."""
        with patch(
            "src.reasoning.nodes.summarization_agent.LLMClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate.return_value = MagicMock(
                text="", success=False, error="Timeout"
            )
            mock_client_class.return_value = mock_client

            node = SummarizationAgentNode()
            result = node.process(sample_rag_state_with_context)

            assert result["error_message"] is not None
            assert "Summarization failure" in result["error_message"]

    def test_latency_tracking(self, sample_rag_state_with_context: RAGState) -> None:
        """Test that latency is tracked."""
        with patch(
            "src.reasoning.nodes.summarization_agent.LLMClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate.return_value = MagicMock(
                text="Test", success=True, error=None
            )
            mock_client_class.return_value = mock_client

            node = SummarizationAgentNode()
            result = node.process(sample_rag_state_with_context)

            assert result["node_latency_ms"]["summarization_agent"] > 0

"""
Unit tests for RetrievalAgentNode.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.reasoning.nodes.retrieval_agent import RetrievalAgentNode
from src.reasoning.state import RAGState


@pytest.mark.unit
class TestRetrievalAgentNode:
    """Test suite for RetrievalAgentNode."""

    def test_process_success(self, sample_rag_state: RAGState) -> None:
        """Test successful retrieval."""
        with (
            patch("src.reasoning.nodes.retrieval_agent.get_retriever") as mock_get_retriever,
            patch("src.reasoning.nodes.retrieval_agent.get_reranker") as mock_get_reranker,
        ):
            mock_retriever = MagicMock()
            mock_retriever.search.return_value = [{"text": "Result 1", "metadata": {"source_file": "doc1.pdf"}}]
            mock_retriever.expand_context.return_value = [
                {
                    "text": "Result 1",
                    "metadata": {"source_file": "doc1.pdf"},
                    "expanded_text": "Result 1",
                }
            ]
            mock_get_retriever.return_value = mock_retriever

            mock_reranker = MagicMock()
            mock_reranker.rerank.return_value = [{"text": "Result 1", "metadata": {"source_file": "doc1.pdf"}}]
            mock_get_reranker.return_value = mock_reranker

            node = RetrievalAgentNode()
            result = node.process(sample_rag_state)

            assert len(result["retrieved_context"]) == 1
            assert result["error_message"] is None
            assert "retrieval_agent" in result["node_latency_ms"]

    def test_process_with_subtasks(self, sample_rag_state: RAGState) -> None:
        """Test retrieval includes sub-tasks in search query."""
        with (
            patch("src.reasoning.nodes.retrieval_agent.get_retriever") as mock_get_retriever,
            patch("src.reasoning.nodes.retrieval_agent.get_reranker") as mock_get_reranker,
        ):
            mock_retriever = MagicMock()
            mock_retriever.search.return_value = []
            mock_retriever.expand_context.return_value = []
            mock_get_retriever.return_value = mock_retriever
            mock_get_reranker.return_value = MagicMock()

            sample_rag_state["sub_tasks"] = ["task1", "task2"]

            node = RetrievalAgentNode()
            node.process(sample_rag_state)

            call_args = mock_retriever.search.call_args[0][0]
            assert "task1" in call_args
            assert "task2" in call_args

    def test_process_error_handling(self, sample_rag_state: RAGState) -> None:
        """Test error handling when retrieval fails."""
        with (
            patch("src.reasoning.nodes.retrieval_agent.get_retriever") as mock_get_retriever,
            patch("src.reasoning.nodes.retrieval_agent.get_reranker") as mock_get_reranker,
        ):
            mock_retriever = MagicMock()
            mock_retriever.search.side_effect = Exception("Connection error")
            mock_get_retriever.return_value = mock_retriever
            mock_get_reranker.return_value = MagicMock()

            node = RetrievalAgentNode()
            result = node.process(sample_rag_state)

            assert result["error_message"] is not None
            assert "Retrieval failure" in result["error_message"]

    def test_latency_tracking(self, sample_rag_state: RAGState) -> None:
        """Test that latency is tracked."""
        with (
            patch("src.reasoning.nodes.retrieval_agent.get_retriever") as mock_get_retriever,
            patch("src.reasoning.nodes.retrieval_agent.get_reranker") as mock_get_reranker,
        ):
            mock_retriever = MagicMock()
            mock_retriever.search.return_value = []
            mock_retriever.expand_context.return_value = []
            mock_get_retriever.return_value = mock_retriever
            mock_get_reranker.return_value = MagicMock()

            node = RetrievalAgentNode()
            result = node.process(sample_rag_state)

            assert result["node_latency_ms"]["retrieval_agent"] > 0

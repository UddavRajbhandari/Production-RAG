"""
Unit tests for AuditorNode.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.reasoning.nodes.auditor import AuditorNode
from src.reasoning.state import RAGState


@pytest.mark.unit
class TestAuditorNode:
    """Test suite for AuditorNode."""

    def test_process_no_hallucination(self, sample_rag_state_with_context: RAGState) -> None:
        """Test when no hallucination detected."""
        with patch("src.reasoning.nodes.auditor.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.return_value = {
                "hallucination": False,
                "missing_claims": [],
            }
            mock_client_class.return_value = mock_client

            node = AuditorNode()
            result = node.process(sample_rag_state_with_context)

            assert result["validation_passed"] is True

    def test_process_hallucination_detected(self, sample_rag_state_with_context: RAGState) -> None:
        """Test when hallucination is detected."""
        with patch("src.reasoning.nodes.auditor.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.return_value = {
                "hallucination": True,
                "missing_claims": ["Claim about X not in context"],
            }
            mock_client_class.return_value = mock_client

            node = AuditorNode()
            result = node.process(sample_rag_state_with_context)

            assert result["validation_passed"] is False
            assert result["error_message"] is not None
            assert "hallucination" in result["error_message"].lower()

    def test_process_fail_open_on_error(self, sample_rag_state_with_context: RAGState) -> None:
        """Test fail-open behavior on system error."""
        with patch("src.reasoning.nodes.auditor.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.side_effect = Exception("System error")
            mock_client_class.return_value = mock_client

            node = AuditorNode()
            result = node.process(sample_rag_state_with_context)

            # Fail open - validation_passed stays unchanged (True)
            assert result["error_message"] is not None
            assert "Auditor system error" in result["error_message"]

    def test_latency_tracking(self, sample_rag_state_with_context: RAGState) -> None:
        """Test that latency is tracked."""
        with patch("src.reasoning.nodes.auditor.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.return_value = {"hallucination": False}
            mock_client_class.return_value = mock_client

            node = AuditorNode()
            result = node.process(sample_rag_state_with_context)

            assert result["node_latency_ms"]["auditor"] > 0

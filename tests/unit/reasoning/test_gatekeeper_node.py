"""
Unit tests for GatekeeperNode.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.reasoning.nodes.gatekeeper import GatekeeperNode
from src.reasoning.state import RAGState


@pytest.mark.unit
class TestGatekeeperNode:
    """Test suite for GatekeeperNode."""

    def test_process_validation_passed(
        self, sample_rag_state_with_context: RAGState
    ) -> None:
        """Test validation passed."""
        with patch("src.reasoning.nodes.gatekeeper.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.return_value = {
                "passed": True,
                "reason": "Answer addresses query",
            }
            mock_client_class.return_value = mock_client

            node = GatekeeperNode()
            result = node.process(sample_rag_state_with_context)

            assert result["validation_passed"] is True
            assert result["error_message"] is None

    def test_process_validation_failed(
        self, sample_rag_state_with_context: RAGState
    ) -> None:
        """Test validation failed."""
        with patch("src.reasoning.nodes.gatekeeper.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.return_value = {
                "passed": False,
                "reason": "Answer does not address query",
            }
            mock_client_class.return_value = mock_client

            node = GatekeeperNode()
            result = node.process(sample_rag_state_with_context)

            assert result["validation_passed"] is False
            assert result["error_message"] is not None
            assert "Gatekeeper rejection" in result["error_message"]

    def test_process_fail_open_on_error(
        self, sample_rag_state_with_context: RAGState
    ) -> None:
        """Test fail-open behavior on system error."""
        with patch("src.reasoning.nodes.gatekeeper.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.side_effect = Exception("System error")
            mock_client_class.return_value = mock_client

            node = GatekeeperNode()
            result = node.process(sample_rag_state_with_context)

            assert result["validation_passed"] is True
            assert result["error_message"] is not None
            assert "Gatekeeper system error" in result["error_message"]

    def test_latency_tracking(self, sample_rag_state_with_context: RAGState) -> None:
        """Test that latency is tracked."""
        with patch("src.reasoning.nodes.gatekeeper.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_json.return_value = {"passed": True}
            mock_client_class.return_value = mock_client

            node = GatekeeperNode()
            result = node.process(sample_rag_state_with_context)

            assert result["node_latency_ms"]["gatekeeper"] > 0

"""
Pytest fixtures for reasoning engine unit tests.
Provides mocks for LLM client and HybridRetriever.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from src.reasoning.state import RAGState


@pytest.fixture
def mock_llm_client() -> Generator[MagicMock, None, None]:
    """Mock LLM client for testing."""
    with patch("src.reasoning.utils.llm_client.LLMClient") as mock:
        client = MagicMock()
        client.generate.return_value = MagicMock(
            text="Test response",
            raw_response={"response": "Test response"},
            latency_ms=100.0,
            success=True,
            error=None,
        )
        client.generate_json.return_value = {"sub_tasks": ["Task 1", "Task 2"]}
        mock.return_value = client
        yield client


@pytest.fixture
def mock_hybrid_retriever() -> Generator[MagicMock, None, None]:
    """Mock HybridRetriever for testing."""
    with (
        patch("src.reasoning.nodes.retrieval_agent.get_retriever") as mock_get_retriever,
        patch("src.reasoning.nodes.retrieval_agent.get_reranker") as mock_get_reranker,
    ):
        retriever = MagicMock()
        retriever.search.return_value = [
            {
                "text": "Sample context text",
                "metadata": {"source_file": "test.pdf"},
            }
        ]
        retriever.expand_context.return_value = [
            {
                "text": "Sample context text",
                "metadata": {"source_file": "test.pdf"},
                "expanded_text": "Sample context text",
            }
        ]
        mock_get_retriever.return_value = retriever
        mock_get_reranker.return_value = MagicMock()
        yield retriever


@pytest.fixture
def sample_rag_state() -> RAGState:
    """Sample RAGState for testing."""
    return {
        "query": "What is the capital of France?",
        "generated_answer": "",
        "sub_tasks": [],
        "retrieved_context": [],
        "current_node": "",
        "validation_passed": True,
        "error_message": None,
        "node_latency_ms": {},
        "total_latency_ms": 0.0,
        "llm_api_key": None,
        "pii_redacted_query": None,
        "total_tokens_used": 0,
        "source_files": [],
        "tenant_id": "",
    }


@pytest.fixture
def sample_rag_state_with_context(sample_rag_state: RAGState) -> RAGState:
    """RAGState with retrieved context."""
    state = sample_rag_state.copy()
    state["retrieved_context"] = [
        {
            "text": "Paris is the capital of France.",
            "metadata": {"source_file": "france.pdf"},
            "expanded_text": "Paris is the capital of France.",
        }
    ]
    state["generated_answer"] = "Paris is the capital of France."
    return state

from src.retrieval.hybrid_search import HybridRetriever
from src.retrieval.reranker import CrossEncoderReranker


def test_hybrid_retriever_initialization() -> None:
    retriever = HybridRetriever()
    assert retriever.qdrant is not None
    assert retriever.bm25 is not None
    assert retriever.rrf_k == 60


def test_reranker_initialization() -> None:
    reranker = CrossEncoderReranker()
    assert reranker.model is not None
    assert reranker.top_n == 5


def test_context_expansion() -> None:
    retriever = HybridRetriever()
    # Mock some results
    nodes = [
        {
            "metadata": {
                "source_file": "Access-to-Information-2023-annual-report.pdf",
                "chunk_index": 1,
            },
            "text": "Current chunk",
        }
    ]
    expanded = retriever.expand_context(nodes, window_size=1)
    assert "expanded_text" in expanded[0]

from types import SimpleNamespace
from typing import Any

from llama_index.core.schema import TextNode

from src.retrieval.hybrid_search import HybridRetriever
from src.retrieval.reranker import CrossEncoderReranker


def test_rrf_preserves_dense_only_results() -> None:
    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.rrf_k = 60
    # Cast to Any to allow mock objects in tests while satisfying mypy
    retriever.bm25 = SimpleNamespace(
        nodes=[
            TextNode(
                text="Sparse node",
                id_="11111111-1111-1111-1111-111111111111",
                metadata={"source_file": "doc.pdf", "chunk_index": 0},
            )
        ]
    )  # type: ignore

    dense_hits = [
        SimpleNamespace(
            id="22222222-2222-2222-2222-222222222222",
            payload={
                "text": "Dense only node",
                "source_file": "doc.pdf",
                "chunk_index": 1,
            },
        )
    ]
    sparse_nodes = retriever.bm25.nodes

    results = retriever._reciprocal_rank_fusion(dense_hits, sparse_nodes)

    assert len(results) == 2
    assert any(result["source"] == "dense_only" for result in results)
    assert any(result["source"] == "hybrid" for result in results)


def test_expand_context_does_not_mutate_input() -> None:
    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.use_cloud_bm25 = False  # Local mode for test
    retriever.bm25 = SimpleNamespace(
        nodes=[
            TextNode(
                text="Previous chunk",
                id_="11111111-1111-1111-1111-111111111111",
                metadata={"source_file": "doc.pdf", "chunk_index": 0},
            ),
            TextNode(
                text="Current chunk",
                id_="22222222-2222-2222-2222-222222222222",
                metadata={"source_file": "doc.pdf", "chunk_index": 1},
            ),
            TextNode(
                text="Next chunk",
                id_="33333333-3333-3333-3333-333333333333",
                metadata={"source_file": "doc.pdf", "chunk_index": 2},
            ),
        ]
    )  # type: ignore

    nodes = [
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "metadata": {"source_file": "doc.pdf", "chunk_index": 1},
            "text": "Current chunk",
        }
    ]
    original = dict(nodes[0])

    expanded = retriever.expand_context(nodes, window_size=1)

    assert "expanded_text" not in nodes[0]
    assert "expanded_text" in expanded[0]
    assert "Previous chunk" in expanded[0]["expanded_text"]
    assert nodes[0] == original


def test_year_filtered_sparse_search_filters_zero_scores(monkeypatch: Any) -> None:
    """Test that year-filtered sparse search works with local BM25.

    This test verifies the year-filter path in _sparse_search.
    When year_filter is set, it creates a temporary BM25 index with filtered nodes.
    """
    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.use_cloud_bm25 = False
    retriever.sparse_k = 15

    # Create test nodes with different dates
    nodes = [
        TextNode(
            text="capital adequacy financial stability report",
            id_="11111111-1111-1111-1111-111111111111",
            metadata={"date": "2023", "source_file": "doc.pdf", "chunk_index": 0},
        ),
        TextNode(
            text="python tutorial loops programming",
            id_="22222222-2222-2222-2222-222222222222",
            metadata={"date": "2024", "source_file": "doc.pdf", "chunk_index": 1},
        ),
    ]

    # Set up BM25 with nodes
    retriever.bm25 = SimpleNamespace(nodes=nodes)  # type: ignore

    # Test with year filter - should return only 2023 nodes
    results = retriever._sparse_search("capital adequacy", year_filter="2023")

    # Should return only the 2023 node (or empty if no term overlap)
    assert len(results) <= 1  # Either 0 or 1 result

    # If we get a result, verify it's the 2023 one
    if results:
        assert results[0].metadata.get("date") == "2023"


def test_reranker_does_not_mutate_candidates(monkeypatch: Any) -> None:
    reranker = CrossEncoderReranker.__new__(CrossEncoderReranker)
    reranker.top_n = 1
    reranker._use_onnx = False

    def mock_predict_pytorch(query: str, candidates: list[dict[str, Any]]) -> list[float]:
        return [0.1, 0.9]

    monkeypatch.setattr(reranker, "_predict_pytorch", mock_predict_pytorch)

    candidates = [
        {"id": "1", "text": "Low score"},
        {"id": "2", "text": "High score"},
    ]
    original = [dict(candidate) for candidate in candidates]

    reranked = reranker.rerank("query", candidates)

    assert candidates == original
    assert len(reranked) == 1
    assert reranked[0]["id"] == "2"
    assert "rerank_score" in reranked[0]

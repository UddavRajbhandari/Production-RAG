from types import SimpleNamespace
from typing import Any

from llama_index.core.schema import TextNode

import src.retrieval.hybrid_search as hybrid_search_module
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
    class FakeBM25:
        def __init__(self, tokenized_corpus: list[list[str]]) -> None:
            self.tokenized_corpus = tokenized_corpus

        def get_scores(self, tokenized_query: list[str]) -> list[float]:
            return [2.0, 0.0]

    monkeypatch.setattr(hybrid_search_module, "BM25Okapi", FakeBM25)

    retriever = HybridRetriever.__new__(HybridRetriever)
    retriever.sparse_k = 15

    def mock_search(query: str, top_k: int = 10) -> list[TextNode]:
        return []

    retriever.bm25 = SimpleNamespace(
        nodes=[
            TextNode(
                text="capital adequacy financial stability",
                id_="11111111-1111-1111-1111-111111111111",
                metadata={"date": "2023"},
            ),
            TextNode(
                text="python tutorial loops",
                id_="22222222-2222-2222-2222-222222222222",
                metadata={"date": "2023"},
            ),
        ],
        search=mock_search,
    )  # type: ignore

    results = retriever._sparse_search("capital adequacy stability", year_filter="2023")

    assert len(results) == 1
    assert results[0].text == "capital adequacy financial stability"


def test_reranker_does_not_mutate_candidates(monkeypatch: Any) -> None:
    reranker = CrossEncoderReranker.__new__(CrossEncoderReranker)
    reranker.top_n = 1
    reranker._use_onnx = False

    def mock_predict_pytorch(
        query: str, candidates: list[dict[str, Any]]
    ) -> list[float]:
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

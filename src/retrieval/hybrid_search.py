"""
Retrieval Infrastructure Module
Implements the Hybrid Search and Context Expansion logic.
Combines dense and sparse results using Reciprocal Rank Fusion (RRF).
"""

import concurrent.futures
import logging
import re
from typing import Any

import yaml
from llama_index.core.schema import TextNode
from qdrant_client.http import models
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from src.storage.bm25_index import BM25Storage
from src.storage.qdrant_client import QdrantStorage

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Coordinator for multi-backend search (Vector + Keyword)."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        """Initializes storage clients and local embedding model."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.qdrant = QdrantStorage()
        self.bm25 = BM25Storage()
        self.bm25.load()

        self.embed_model = SentenceTransformer(self.config["models"]["embedding"])

        self.dense_k = self.config["retrieval"]["dense_top_k"]
        self.sparse_k = self.config["retrieval"]["sparse_top_k"]
        self.rrf_k = self.config["retrieval"]["rrf_k"]
        self.rerank_pool_size = self.config["retrieval"]["rerank_pool_size"]

        # Speed Optimization: Persistent thread pool to avoid spawn overhead
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def search(self, query: str) -> list[dict[str, Any]]:
        """
        Executes parallel dense and sparse searches.
        Applies Reciprocal Rank Fusion (RRF) and returns top candidates.
        """
        # Accuracy Optimization: Metadata Filter Extraction
        year_filter = self._extract_year_filter(query)

        # Speed Optimization: Parallel Retrieval using persistent executor
        dense_future = self._executor.submit(self._dense_search, query, year_filter)
        sparse_future = self._executor.submit(self._sparse_search, query, year_filter)

        dense_results = dense_future.result()
        sparse_results = sparse_future.result()

        # 3. Reciprocal Rank Fusion (RRF)
        fused_results = self._reciprocal_rank_fusion(dense_results, sparse_results)

        # Speed Optimization: Prune candidate pool for the reranker
        return fused_results[: self.rerank_pool_size]

    def expand_context(
        self, nodes: list[dict[str, Any]], window_size: int = 1
    ) -> list[dict[str, Any]]:
        """
        Returns a new list of result dicts enriched with surrounding chunk text.
        """
        node_lookup: dict[tuple[str, int], TextNode] = {
            (n.metadata["source_file"], n.metadata["chunk_index"]): n
            for n in self.bm25.nodes
        }
        expanded: list[dict[str, Any]] = []

        for node_dict in nodes:
            source = node_dict["metadata"].get("source_file", "")
            idx = node_dict["metadata"].get("chunk_index", 0)

            context_parts: list[str] = []
            for i in range(idx - window_size, idx + window_size + 1):
                neighbour = node_lookup.get((source, i))
                if neighbour is not None:
                    context_parts.append(neighbour.text)
                elif i != idx:
                    logger.debug(
                        "expand_context: chunk (%s, %d) not found — boundary chunk.",
                        source,
                        i,
                    )

            enriched = {**node_dict, "expanded_text": "\n\n".join(context_parts)}
            expanded.append(enriched)

        return expanded

    def _extract_year_filter(self, query: str) -> str | None:
        """Extracts years like 2023 or FY23 from the query."""
        match = re.search(r"(20\d{2}|FY\d{2})", query)
        return match.group(1) if match else None

    def _dense_search(self, query: str, year_filter: str | None = None) -> list[Any]:
        """Vector search against Qdrant with optional hard metadata filters."""
        query_vector = self.embed_model.encode(query).tolist()

        # Accuracy Optimization: Hard filtering by year if present
        query_filter = None
        if year_filter:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="date", match=models.MatchValue(value=year_filter)
                    )
                ]
            )

        # Fetch points and ensure we return a list
        response = self.qdrant.client.query_points(
            collection_name=self.qdrant.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=self.dense_k,
        )
        return list(response.points)

    def _sparse_search(
        self, query: str, year_filter: str | None = None
    ) -> list[TextNode]:
        """Keyword search against BM25 with optional year pre-filtering."""
        if year_filter:
            filtered_nodes = [
                n for n in self.bm25.nodes if n.metadata.get("date") == year_filter
            ]
            if not filtered_nodes:
                logger.warning(
                    "Year filter '%s' matched 0 nodes — falling back to full index.",
                    year_filter,
                )
                return self.bm25.search(query, top_k=self.sparse_k)

            tokenized_corpus = [node.text.lower().split() for node in filtered_nodes]
            temp_bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = query.lower().split()
            raw_scores = temp_bm25.get_scores(tokenized_query)
            scored = [
                (i, float(raw_scores[i]))
                for i in range(len(raw_scores))
                if float(raw_scores[i]) > 0.0
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [filtered_nodes[i] for i, _ in scored[: self.sparse_k]]

        return self.bm25.search(query, top_k=self.sparse_k)

    def _reciprocal_rank_fusion(
        self, dense_hits: list[Any], sparse_nodes: list[TextNode]
    ) -> list[dict[str, Any]]:
        """Merges dense and sparse results using Reciprocal Rank Fusion."""
        scores: dict[str, float] = {}

        for rank, hit in enumerate(dense_hits):
            node_id = str(hit.id)
            scores[node_id] = scores.get(node_id, 0.0) + 1.0 / (self.rrf_k + rank + 1)

        for rank, node in enumerate(sparse_nodes):
            node_id = str(node.id_)
            scores[node_id] = scores.get(node_id, 0.0) + 1.0 / (self.rrf_k + rank + 1)

        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        bm25_lookup: dict[str, TextNode] = {node.id_: node for node in self.bm25.nodes}
        qdrant_lookup: dict[str, Any] = {str(hit.id): hit for hit in dense_hits}

        final_results: list[dict[str, Any]] = []
        for node_id, rrf_score in sorted_ids:
            if node_id in bm25_lookup:
                node = bm25_lookup[node_id]
                final_results.append(
                    {
                        "id": node_id,
                        "text": node.text,
                        "metadata": node.metadata,
                        "rrf_score": rrf_score,
                        "source": "hybrid",
                    }
                )
            elif node_id in qdrant_lookup:
                hit = qdrant_lookup[node_id]
                payload = dict(hit.payload or {})
                text = payload.pop("text", "")
                final_results.append(
                    {
                        "id": node_id,
                        "text": text,
                        "metadata": payload,
                        "rrf_score": rrf_score,
                        "source": "dense_only",
                    }
                )
            else:
                logger.warning(
                    "Node ID %s has an RRF score but was not found in any lookup.",
                    node_id,
                )

        return final_results

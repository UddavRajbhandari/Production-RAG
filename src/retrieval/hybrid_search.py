"""
Retrieval Infrastructure Module
Implements the Hybrid Search and Context Expansion logic.
Combines dense and sparse results using Reciprocal Rank Fusion (RRF).
"""

import concurrent.futures
import re
from typing import Any

import yaml
from llama_index.core.schema import TextNode
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

from src.storage.bm25_index import BM25Storage
from src.storage.qdrant_client import QdrantStorage


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
        # Limit candidates for reranking to improve speed (Balance: Speed + Accuracy)
        self.rerank_pool_size = 15

    def search(self, query: str) -> list[dict[str, Any]]:
        """
        Executes parallel dense and sparse searches.
        Applies Reciprocal Rank Fusion (RRF) and returns top candidates.
        """
        # Accuracy Optimization: Metadata Filter Extraction
        year_filter = self._extract_year_filter(query)

        # Speed Optimization: Parallel Retrieval
        with concurrent.futures.ThreadPoolExecutor() as executor:
            dense_future = executor.submit(self._dense_search, query, year_filter)
            sparse_future = executor.submit(self._sparse_search, query, year_filter)

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
        Accuracy Optimization: Fetches surrounding chunks to enrich context.
        Uses chunk_index and source_file for precise lookup.
        """
        expanded_nodes = []
        node_lookup = {
            (n.metadata["source_file"], n.metadata["chunk_index"]): n
            for n in self.bm25.nodes
        }

        for node_dict in nodes:
            source = node_dict["metadata"]["source_file"]
            idx = node_dict["metadata"]["chunk_index"]

            context_text = []
            # Fetch preceding, current, and succeeding
            for i in range(idx - window_size, idx + window_size + 1):
                if (source, i) in node_lookup:
                    context_text.append(node_lookup[(source, i)].text)

            node_dict["expanded_text"] = "\n\n".join(context_text)
            expanded_nodes.append(node_dict)

        return expanded_nodes

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
        """Keyword search against BM25 index with node pre-filtering."""
        if year_filter:
            filtered_nodes = [
                n for n in self.bm25.nodes if n.metadata.get("date") == year_filter
            ]
            if not filtered_nodes:  # Fallback to all nodes if filter returns zero
                return self.bm25.search(query, top_k=self.sparse_k)

            # Re-index only filtered nodes for maximum accuracy
            tokenized_corpus = [node.text.lower().split() for node in filtered_nodes]
            from rank_bm25 import BM25Okapi

            temp_bm25 = BM25Okapi(tokenized_corpus)

            tokenized_query = query.lower().split()
            scores = temp_bm25.get_scores(tokenized_query)
            top_n = sorted(
                range(len(scores)), key=lambda i: float(scores[i]), reverse=True
            )[: self.sparse_k]
            return [filtered_nodes[i] for i in top_n]

        return self.bm25.search(query, top_k=self.sparse_k)

    def _reciprocal_rank_fusion(
        self, dense_hits: list[Any], sparse_nodes: list[TextNode]
    ) -> list[dict[str, Any]]:
        """Merges disparate result lists into a single ranked list using RRF formula."""
        scores: dict[str, float] = {}

        for rank, hit in enumerate(dense_hits):
            node_id = str(hit.id)
            scores[node_id] = scores.get(node_id, 0.0) + 1.0 / (self.rrf_k + rank + 1)

        for rank, node in enumerate(sparse_nodes):
            node_id = str(node.id_)
            scores[node_id] = scores.get(node_id, 0.0) + 1.0 / (self.rrf_k + rank + 1)

        # Sort by score
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        node_lookup = {node.id_: node for node in self.bm25.nodes}

        final_results = []
        for node_id, rrf_score in sorted_ids:
            if node_id in node_lookup:
                node = node_lookup[node_id]
                final_results.append(
                    {
                        "id": node_id,
                        "text": node.text,
                        "metadata": node.metadata,
                        "rrf_score": rrf_score,
                    }
                )

        return final_results

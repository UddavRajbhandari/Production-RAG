"""
Retrieval Infrastructure Module
Implements the Hybrid Search and Context Expansion logic.
Combines dense and sparse results using Reciprocal Rank Fusion (RRF).

Supports dual BM25 modes:
- Cloud mode: Uses Qdrant native sparse vectors (fast, server-side)
- Local mode: Uses local pickle BM25 (development/fallback)
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import re
from typing import TYPE_CHECKING, Any

import yaml

from src.storage.bm25_storage import BM25Storage
from src.storage.qdrant_sparse_storage import QdrantSparseStorage
from src.storage.qdrant_storage import QdrantStorage

if TYPE_CHECKING:
    from llama_index.core.schema import TextNode


logger = logging.getLogger(__name__)


def should_use_qdrant_bm25() -> bool:
    """Check if Qdrant Cloud with native BM25 is available."""
    return bool(os.getenv("QDRANT_URL"))


class HybridRetriever:
    """Coordinator for multi-backend search (Vector + Keyword)."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        """Initializes storage clients and local embedding model."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.qdrant = QdrantStorage()

        self.use_cloud_bm25 = should_use_qdrant_bm25()
        self.bm25: BM25Storage | QdrantSparseStorage

        if self.use_cloud_bm25:
            self.bm25 = QdrantSparseStorage()
            logger.info("HybridRetriever: Using Qdrant native BM25 (cloud mode)")
        else:
            self.bm25 = BM25Storage()
            self.bm25.load()
            logger.info("HybridRetriever: Using local BM25 pickle (local mode)")

        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        self.embed_model = SentenceTransformer(self.config["models"]["embedding"])

        self.dense_k = self.config["retrieval"]["dense_top_k"]
        self.sparse_k = self.config["retrieval"]["sparse_top_k"]
        self.rrf_k = self.config["retrieval"]["rrf_k"]
        self.rerank_pool_size = self.config["retrieval"]["rerank_pool_size"]

        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def reload_bm25(self) -> None:
        """Reload BM25 index from disk after incremental ingest."""
        if not self.use_cloud_bm25 and isinstance(self.bm25, BM25Storage):
            try:
                self.bm25.load()
                logger.info("BM25 index reloaded from disk")
            except Exception as e:
                logger.warning("Failed to reload BM25 index: %s", e)

    def search(self, query: str, source_files: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Executes parallel dense and sparse searches.
        Applies Reciprocal Rank Fusion (RRF) and returns top candidates.

        Args:
            query: The search query text
            source_files: Optional list of source filenames to filter by.
                When provided, only chunks from these files are returned.
        """
        year_filter = self._extract_year_filter(query)

        dense_future = self._executor.submit(self._dense_search, query, year_filter, source_files)
        sparse_future = self._executor.submit(self._sparse_search, query, year_filter, source_files)

        dense_results = dense_future.result()
        sparse_results = sparse_future.result()

        fused_results = self._reciprocal_rank_fusion(dense_results, sparse_results)

        return fused_results[: self.rerank_pool_size]

    def expand_context(self, nodes: list[dict[str, Any]], window_size: int = 1) -> list[dict[str, Any]]:
        """
        Returns a new list of result dicts enriched with surrounding chunk text.

        In local mode: Uses BM25 nodes for context lookup
        In cloud mode: Uses Neon Postgres for context lookup (via payload)
        """
        if self.use_cloud_bm25:
            return self._expand_context_cloud(nodes, window_size)
        return self._expand_context_local(nodes, window_size)

    def _expand_context_local(self, nodes: list[dict[str, Any]], window_size: int = 1) -> list[dict[str, Any]]:
        """Expand context using local BM25 nodes."""
        if hasattr(self.bm25, "nodes"):
            node_lookup: dict[tuple[str, int], TextNode] = {
                (n.metadata["source_file"], n.metadata["chunk_index"]): n for n in self.bm25.nodes
            }
            return self._do_expand_context(nodes, node_lookup, window_size)
        return nodes

    def _expand_context_cloud(self, nodes: list[dict[str, Any]], window_size: int = 1) -> list[dict[str, Any]]:
        """Expand context using Qdrant payload metadata."""
        try:
            from src.storage.neon_storage import NeonStorage

            neon = NeonStorage()
            node_lookup: dict[tuple[str, int], dict] = {}

            for node_dict in nodes:
                source = node_dict["metadata"].get("source_file")
                chunk_idx = node_dict["metadata"].get("chunk_index")
                if source and chunk_idx is not None:
                    for i in range(chunk_idx - window_size, chunk_idx + window_size + 1):
                        if (source, i) not in node_lookup:
                            try:
                                chunks = neon.get_chunks_by_source_file(source)
                                for c in chunks:
                                    if getattr(c, "chunk_index", None) == i:
                                        node_lookup[(source, i)] = {
                                            "text": c.text,
                                            "metadata": {
                                                "source_file": c.source_file,
                                                "chunk_index": getattr(c, "chunk_index", None),
                                            },
                                        }
                            except Exception as e:
                                logger.warning("Failed to get chunks from Neon: %s", e)
                                break

            return self._do_expand_context(nodes, node_lookup, window_size)
        except Exception as e:
            logger.warning("Context expansion failed: %s", e)
            return nodes

    def _do_expand_context(
        self,
        nodes: list[dict[str, Any]],
        node_lookup: dict[tuple[str, int], Any],
        window_size: int,
    ) -> list[dict[str, Any]]:
        """Core context expansion logic."""
        expanded: list[dict[str, Any]] = []

        for node_dict in nodes:
            source = node_dict["metadata"].get("source_file", "")
            idx = node_dict["metadata"].get("chunk_index", 0)

            context_parts: list[str] = []
            for i in range(idx - window_size, idx + window_size + 1):
                neighbour = node_lookup.get((source, i))
                if neighbour is not None:
                    if hasattr(neighbour, "text"):
                        context_parts.append(neighbour.text)
                    else:
                        context_parts.append(neighbour.get("text", ""))
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
        """Extracts years like 2023 or FY23 from the query and normalizes to YYYY."""
        match = re.search(r"(20\d{2}|FY(\d{2}))", query)
        if not match:
            return None

        year = match.group(1)
        if year.startswith("FY"):
            short_year = match.group(2)
            return f"20{short_year}"
        return year

    def _dense_search(
        self,
        query: str,
        year_filter: str | None = None,
        source_files: list[str] | None = None,
    ) -> list[Any]:
        """Vector search against Qdrant with optional hard metadata filters."""
        query_vector = self.embed_model.encode(query).tolist()

        query_filter = None
        filter_conditions = []
        if year_filter and self.use_cloud_bm25:
            try:
                from qdrant_client.http import models  # noqa: PLC0415

                filter_conditions.append(
                    models.FieldCondition(key="date", match=models.MatchValue(value=year_filter)),
                )
            except Exception as e:
                logger.warning("Failed to create date filter: %s - proceeding without filter", e)

        if source_files:
            try:
                from qdrant_client.http import models  # noqa: PLC0415

                source_conditions = [
                    models.FieldCondition(key="source_file", match=models.MatchValue(value=sf)) for sf in source_files
                ]
                if len(source_conditions) == 1:
                    filter_conditions.append(source_conditions[0])
                else:
                    filter_conditions.append(
                        models.FieldCondition(
                            key="source_file",
                            match=models.MatchAny(any=list(source_files)),
                        ),
                    )
            except Exception as e:
                logger.warning("Failed to create source_file filter: %s", e)

        if filter_conditions:
            from qdrant_client.http import models  # noqa: PLC0415

            query_filter = models.Filter(must=list(filter_conditions))

        try:
            if self.use_cloud_bm25:
                response = self.qdrant.client.query_points(
                    collection_name=self.qdrant.collection_name,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=self.dense_k,
                    using="dense",
                )
            else:
                response = self.qdrant.client.query_points(
                    collection_name=self.qdrant.collection_name,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=self.dense_k,
                )
            return list(response.points)
        except Exception as e:
            logger.warning("Dense search failed with filter, retrying without: %s", e)
            try:
                if self.use_cloud_bm25:
                    response = self.qdrant.client.query_points(
                        collection_name=self.qdrant.collection_name,
                        query=query_vector,
                        limit=self.dense_k,
                        using="dense",
                    )
                else:
                    response = self.qdrant.client.query_points(
                        collection_name=self.qdrant.collection_name,
                        query=query_vector,
                        limit=self.dense_k,
                    )
                return list(response.points)
            except Exception as e2:
                logger.error("Dense search failed completely: %s", e2)
                return []

    def _sparse_search(
        self,
        query: str,
        year_filter: str | None = None,
        source_files: list[str] | None = None,
    ) -> list[TextNode]:
        """Keyword search using appropriate BM25 backend (cloud or local)."""
        if self.use_cloud_bm25:
            return self.bm25.search(query, top_k=self.sparse_k, source_files=source_files)  # type: ignore[call-arg]

        nodes = self.bm25.nodes
        if source_files:
            source_set = set(source_files)
            nodes = [n for n in nodes if n.metadata.get("source_file") in source_set]

        if year_filter:
            filtered_nodes = [n for n in nodes if n.metadata.get("date") == year_filter]
            if not filtered_nodes:
                logger.warning(
                    "Year filter '%s' matched 0 nodes — falling back to filtered nodes.",
                    year_filter,
                )
                from rank_bm25 import BM25Okapi

                tokenized_corpus = [n.text.lower().split() for n in nodes]
                temp_bm25 = BM25Okapi(tokenized_corpus)
                tokenized_query = query.lower().split()
                raw_scores = temp_bm25.get_scores(tokenized_query)
                scored = [(i, float(raw_scores[i])) for i in range(len(raw_scores)) if float(raw_scores[i]) > 0.0]
                scored.sort(key=lambda x: x[1], reverse=True)
                return [nodes[i] for i, _ in scored[: self.sparse_k]]

            from rank_bm25 import BM25Okapi

            tokenized_corpus = [n.text.lower().split() for n in filtered_nodes]
            temp_bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = query.lower().split()
            raw_scores = temp_bm25.get_scores(tokenized_query)
            scored = [(i, float(raw_scores[i])) for i in range(len(raw_scores)) if float(raw_scores[i]) > 0.0]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [filtered_nodes[i] for i, _ in scored[: self.sparse_k]]

        if source_files or nodes is not self.bm25.nodes:
            from rank_bm25 import BM25Okapi

            tokenized_corpus = [n.text.lower().split() for n in nodes]
            temp_bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = query.lower().split()
            raw_scores = temp_bm25.get_scores(tokenized_query)
            scored = [(i, float(raw_scores[i])) for i in range(len(raw_scores)) if float(raw_scores[i]) > 0.0]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [nodes[i] for i, _ in scored[: self.sparse_k]]

        return self.bm25.search(query, top_k=self.sparse_k)

    def _reciprocal_rank_fusion(self, dense_hits: list[Any], sparse_nodes: list[TextNode]) -> list[dict[str, Any]]:
        """Merges dense and sparse results using Reciprocal Rank Fusion."""
        scores: dict[str, float] = {}

        for rank, hit in enumerate(dense_hits):
            node_id = str(hit.id)
            scores[node_id] = scores.get(node_id, 0.0) + 1.0 / (self.rrf_k + rank + 1)

        for rank, node in enumerate(sparse_nodes):
            node_id = str(node.id_)
            scores[node_id] = scores.get(node_id, 0.0) + 1.0 / (self.rrf_k + rank + 1)

        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        bm25_lookup: dict[str, TextNode] = (
            {node.id_: node for node in self.bm25.nodes} if hasattr(self.bm25, "nodes") else {}
        )
        sparse_lookup: dict[str, TextNode] = {str(n.id_): n for n in sparse_nodes}
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
            elif node_id in sparse_lookup:
                node = sparse_lookup[node_id]
                final_results.append(
                    {
                        "id": node_id,
                        "text": node.text,
                        "metadata": node.metadata,
                        "rrf_score": rrf_score,
                        "source": "sparse_only",
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

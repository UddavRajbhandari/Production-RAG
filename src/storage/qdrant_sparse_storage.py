"""
Qdrant Sparse Storage Module
Manages sparse vector indexing for native BM25 using Qdrant Cloud inference.

This module provides keyword search via Qdrant's built-in BM25 scoring,
which is faster and more scalable than local pickle-based BM25.

Requirements:
- Qdrant Cloud cluster with inference enabled
- QDRANT_URL and QDRANT_API_KEY environment variables

Usage:
    sparse = QdrantSparseStorage()
    sparse.upsert_with_bm25(nodes)  # Batch upsert with BM25 vectors
    results = sparse.search("query text", top_k=10)
"""

import logging
import uuid

from llama_index.core.schema import TextNode
from qdrant_client.http import models

from src.storage.qdrant_storage import QdrantStorage

logger = logging.getLogger(__name__)

# Smaller batch size for cloud uploads to avoid timeout
_BATCH_SIZE = 32
_UPSERT_TIMEOUT = 120  # seconds


class QdrantSparseStorage:
    """
    Qdrant native sparse vector storage for BM25.

    Uses server-side inference for BM25 scoring via Qdrant Cloud.
    Falls back to local BM25Storage if cloud is unavailable.
    """

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        self.qdrant = QdrantStorage()
        self.collection_name = self.qdrant.collection_name
        self.client = self.qdrant.client

        self.vector_name = "sparse-bm25"
        self.model = "Qdrant/bm25"
        self.mode = "qdrant_native"

        # Compatibility with BM25Storage interface
        self.nodes: list[TextNode] = []

        logger.info(
            "QdrantSparseStorage initialized (collection=%s, model=%s)",
            self.collection_name,
            self.model,
        )

    def build_index(self, nodes: list[TextNode]) -> None:
        """No-op for cloud storage (index is server-side)."""
        pass

    def save(self) -> None:
        """No-op for cloud storage (persist is server-side)."""
        pass

    def load(self) -> None:
        """No-op for cloud storage."""
        pass

    def upsert_with_bm25(self, nodes: list[TextNode], batch_size: int = _BATCH_SIZE) -> None:
        """
        Upsert nodes with BM25 sparse vectors.

        Uses Qdrant's Document inference to generate sparse vectors
        directly on the server.

        Args:
            nodes: List of TextNode objects to upsert
            batch_size: Number of points per batch (default 32 for cloud)
        """
        if not nodes:
            return

        total = len(nodes)
        logger.info("Upserting %d nodes with BM25 sparse vectors (batch=%d)", total, batch_size)

        for start in range(0, total, batch_size):
            batch = nodes[start : start + batch_size]
            points = []

            for node in batch:
                point_id = self._validated_uuid(node.id_)
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector={
                            self.vector_name: models.Document(
                                text=node.text,
                                model=self.model,
                            )
                        },
                        payload={
                            "text": node.text,
                            "id_": node.id_,
                            **node.metadata,
                        },
                    )
                )

            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                timeout=_UPSERT_TIMEOUT,
            )

            logger.info(
                "Upserted %d/%d points with BM25",
                min(start + batch_size, total),
                total,
            )

    def upsert_dense_and_bm25(
        self,
        nodes: list[TextNode],
        embeddings: list[list[float]],
        batch_size: int = _BATCH_SIZE,
    ) -> None:
        """
        Upsert nodes with both dense vectors and BM25 sparse vectors.

        This is the primary method for hybrid search storage.

        Args:
            nodes: List of TextNode objects
            embeddings: List of dense vectors (same order as nodes)
            batch_size: Number of points per batch
        """
        if len(nodes) != len(embeddings):
            raise ValueError(f"nodes ({len(nodes)}) and embeddings ({len(embeddings)}) must have same length.")

        total = len(nodes)
        logger.info("Upserting %d nodes with dense + BM25 sparse vectors", total)

        for start in range(0, total, batch_size):
            batch_nodes = nodes[start : start + batch_size]
            batch_embeddings = embeddings[start : start + batch_size]
            points = []

            for node, embedding in zip(batch_nodes, batch_embeddings, strict=True):
                point_id = self._validated_uuid(node.id_)
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector={
                            "dense": embedding,
                            self.vector_name: models.Document(
                                text=node.text,
                                model=self.model,
                            ),
                        },
                        payload={
                            "text": node.text,
                            "id_": node.id_,
                            **node.metadata,
                        },
                    )
                )

            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                timeout=_UPSERT_TIMEOUT,
            )

            logger.info(
                "Upserted %d/%d points with dense + BM25",
                min(start + batch_size, total),
                total,
            )

    def search(self, query: str, top_k: int = 10, source_files: list[str] | None = None) -> list[TextNode]:
        """
        Search using BM25 sparse vectors via server-side inference.

        Args:
            query: Query text
            top_k: Number of results to return
            source_files: Optional list of source filenames to filter by

        Returns:
            List of TextNode objects matching the query
        """
        qfilter = None
        if source_files:
            qfilter = models.Filter(
                should=[
                    models.FieldCondition(key="source_file", match=models.MatchValue(value=sf)) for sf in source_files
                ],
            )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=models.Document(text=query, model=self.model),
            using=self.vector_name,
            query_filter=qfilter,
            limit=top_k,
        )

        nodes = []
        for hit in results.points:
            payload = dict(hit.payload or {})
            text = payload.pop("text", "")
            node_id = payload.pop("id_", str(hit.id))

            nodes.append(
                TextNode(
                    id_=node_id,
                    text=text,
                    metadata=payload,
                )
            )

        logger.debug("BM25 search returned %d results for query '%s'", len(nodes), query[:50])
        return nodes

    def search_with_scores(self, query: str, top_k: int = 10) -> list[tuple[TextNode, float]]:
        """
        Search using BM25 with score information.

        Returns tuples of (TextNode, bm25_score).
        """
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=models.Document(text=query, model=self.model),
            using=self.vector_name,
            limit=top_k,
        )

        scored_results = []
        for hit in results.points:
            payload = dict(hit.payload or {})
            text = payload.pop("text", "")
            node_id = payload.pop("id_", str(hit.id))
            score = hit.score or 0.0

            node = TextNode(
                id_=node_id,
                text=text,
                metadata=payload,
            )
            scored_results.append((node, score))

        return scored_results

    def hybrid_search(
        self,
        query: str,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[dict]:
        """
        Perform hybrid search combining dense and sparse (BM25).

        This is the recommended search method for production.

        Args:
            query: Query text (for BM25)
            query_vector: Dense embedding vector
            top_k: Number of results

        Returns:
            List of result dicts with text, metadata, and scores
        """
        dense_results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using="dense",
            limit=top_k * 2,
        )

        sparse_results = self.client.query_points(
            collection_name=self.collection_name,
            query=models.Document(text=query, model=self.model),
            using=self.vector_name,
            limit=top_k * 2,
        )

        dense_lookup = {str(p.id): p for p in dense_results.points}
        sparse_lookup = {str(p.id): p for p in sparse_results.points}

        rrf_scores: dict[str, float] = {}
        for rank, hit in enumerate(dense_results.points):
            rrf_scores[str(hit.id)] = rrf_scores.get(str(hit.id), 0) + 1.0 / (60 + rank + 1)
        for rank, hit in enumerate(sparse_results.points):
            rrf_scores[str(hit.id)] = rrf_scores.get(str(hit.id), 0) + 1.0 / (60 + rank + 1)

        sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for node_id, rrf_score in sorted_ids:
            payload = {}
            if node_id in dense_lookup:
                payload = dict(dense_lookup[node_id].payload or {})
            elif node_id in sparse_lookup:
                payload = dict(sparse_lookup[node_id].payload or {})

            text = payload.pop("text", "")
            metadata = {**payload, "node_id": node_id}

            results.append(
                {
                    "id": node_id,
                    "text": text,
                    "metadata": metadata,
                    "rrf_score": rrf_score,
                    "source": "hybrid",
                }
            )

        return results

    @staticmethod
    def _validated_uuid(raw_id: str) -> str:
        """Validate and convert node ID to UUID format."""
        import hashlib

        try:
            return str(uuid.UUID(str(raw_id)))
        except (ValueError, AttributeError):
            if raw_id.startswith(("sa_", "naive_")):
                hash_hex = hashlib.sha256(raw_id.encode()).hexdigest()[:32]
                return str(uuid.UUID(hash_hex))
            raise ValueError(
                f"Node ID '{raw_id}' is not a valid UUID. Qdrant requires UUID-format strings or unsigned integers."
            ) from None

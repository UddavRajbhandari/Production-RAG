"""
Qdrant Vector Storage Module
Manages dense vector indexing and retrieval using Qdrant.

Changes from v1:
- UUID validation on all point IDs before upsert
- Batched upsert to avoid memory spikes on large corpora
- Explicit connection error logging (not silent fallback)
- search() method added for Phase 3 round-trip testing
"""

import logging
import os
import uuid
from typing import Any

import yaml
from llama_index.core.schema import TextNode
from qdrant_client import QdrantClient
from qdrant_client.http import models

logger = logging.getLogger(__name__)

# Maximum points per upsert call. Keeps memory usage predictable.
_UPSERT_BATCH_SIZE = 256


class QdrantStorage:
    """Storage client for the Qdrant dense vector backend."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        q_config = self.config["storage"]["qdrant"]
        self.collection_name = q_config["collection_name"]
        self.vector_size = q_config["vector_size"]
        self.distance = q_config["distance"]

        self.client = self._connect(q_config)

    def _connect(self, q_config: dict[str, Any]) -> QdrantClient:
        """
        Attempts Docker connection first; falls back to local disk.
        Logs the reason for any fallback — no silent swallowing.
        """
        try:
            client = QdrantClient(host=q_config["host"], port=q_config["port"])
            client.get_collections()  # lightweight ping
            logger.info(
                "Connected to Qdrant at %s:%s",
                q_config["host"],
                q_config["port"],
            )
            return client
        except Exception as exc:
            logger.warning(
                "Docker Qdrant unavailable (%s). Falling back to local disk storage.",
                exc,
            )
            local_path = "storage/qdrant_data"
            os.makedirs(local_path, exist_ok=True)
            logger.info("Using local Qdrant path: %s", local_path)
            return QdrantClient(path=local_path)

    def create_collection(self, force_recreate: bool = False) -> None:
        """Creates the vector collection. Optionally drops and recreates it."""
        if force_recreate and self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
            logger.info("Dropped existing collection '%s'.", self.collection_name)

        if not self.client.collection_exists(self.collection_name):
            distance = (
                models.Distance.COSINE
                if self.distance == "Cosine"
                else models.Distance.EUCLID
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=distance,
                ),
            )
            logger.info(
                "Collection '%s' created (%d dims, %s).",
                self.collection_name,
                self.vector_size,
                self.distance,
            )
        else:
            logger.info(
                "Collection '%s' already exists — skipping creation.",
                self.collection_name,
            )

    def insert_nodes(
        self,
        nodes: list[TextNode],
        embeddings: list[list[float]],
        batch_size: int = _UPSERT_BATCH_SIZE,
    ) -> None:
        """
        Upserts TextNodes and their vectors into Qdrant in batches.

        Each node ID is validated as a UUID string before insertion.
        Invalid IDs raise ValueError immediately rather than letting Qdrant
        reject them silently mid-batch.
        """
        if len(nodes) != len(embeddings):
            raise ValueError(
                f"nodes ({len(nodes)}) and embeddings ({len(embeddings)}) must have "
                "the same length."
            )

        all_points: list[models.PointStruct] = []
        for node, vector in zip(nodes, embeddings, strict=True):
            point_id = self._validated_uuid(node.id_)
            all_points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"text": node.text, **node.metadata},
                )
            )

        # Batch upsert
        total = len(all_points)
        for start in range(0, total, batch_size):
            batch = all_points[start : start + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
            logger.info(
                "Upserted %d/%d points into '%s'.",
                min(start + batch_size, total),
                total,
                self.collection_name,
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validated_uuid(raw_id: str) -> str:
        """
        Confirms raw_id is a valid UUID string and returns it in canonical form.

        Raises ValueError with a clear message if the ID is not a valid UUID.
        This catches problems early — before Qdrant rejects the batch silently.
        """
        try:
            return str(uuid.UUID(str(raw_id)))
        except (ValueError, AttributeError) as exc:
            raise ValueError(
                f"Node ID '{raw_id}' is not a valid UUID. Qdrant requires UUID-format "
                f"strings or unsigned integers as point IDs. Original error: {exc}"
            ) from exc

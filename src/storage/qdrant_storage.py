"""
Qdrant Vector Storage Module
Manages dense vector indexing and retrieval using Qdrant.

Changes from v1:
- Cloud support: QDRANT_URL env var for Qdrant Cloud with native BM25
- Local fallback: Docker or local path if cloud unavailable
- Sparse vectors: Optional sparse-bm25 for native BM25 support
- Mode detection: Logs connection mode at startup

Storage Priority:
1. QDRANT_URL (cloud) → Qdrant Cloud with native BM25
2. QDRANT_HOST:PORT (Docker) → Local development
3. localhost:6333 default → Fallback
"""

import hashlib
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
# Smaller for cloud to avoid timeout
_UPSERT_BATCH_SIZE = 32
_UPSERT_TIMEOUT = 120  # seconds


def get_qdrant_mode() -> str:
    """Detect Qdrant connection mode from environment."""
    if os.getenv("QDRANT_URL"):
        return "cloud"
    elif os.getenv("QDRANT_HOST"):
        return "docker"
    return "local"


def should_use_qdrant_bm25() -> bool:
    """Check if Qdrant Cloud with inference is available for native BM25."""
    return bool(os.getenv("QDRANT_URL"))


class QdrantStorage:
    """Storage client for the Qdrant dense vector backend."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        q_config = self.config["storage"]["qdrant"]
        self.collection_name = q_config["collection_name"]
        self.vector_size = q_config["vector_size"]
        self.distance = q_config["distance"]

        # Auto-append chunker suffix for Phase 6 iteration comparison
        # e.g., "production_rag_v1" -> "production_rag_v1_naive"
        if q_config.get("use_chunker_suffix", True):
            ing = self.config.get("ingestion", {})
            chunker_type = ing.get("chunker_type", "structure_aware")
            self.collection_name = f"{self.collection_name}_{chunker_type}"

        # Detect connection mode
        self.mode = get_qdrant_mode()
        logger.info("QdrantStorage initialized in %s mode", self.mode)

        self.client = self._connect(q_config)

    def _connect(self, q_config: dict[str, Any]) -> QdrantClient:
        """
        Connects to Qdrant in the following priority:
        1. QDRANT_URL (cloud) → Qdrant Cloud with inference support
        2. QDRANT_HOST:PORT (Docker) → Local development
        3. localhost:6333 default → Docker fallback
        4. Local disk path → Emergency fallback
        """
        # Priority 1: Cloud URL
        if qdrant_url := os.getenv("QDRANT_URL"):
            api_key = os.getenv("QDRANT_API_KEY", "")

            client = QdrantClient(
                url=qdrant_url,
                api_key=api_key if api_key else None,
            )
            try:
                client.get_collections()
                logger.info("Connected to Qdrant Cloud at %s", qdrant_url)
                self.enable_sparse_vectors = True
                return client
            except Exception as exc:
                logger.error("Qdrant Cloud connection failed: %s", exc)
                raise

        # Priority 2: Docker (QDRANT_HOST:PORT)
        host = q_config.get("host", "localhost")
        port = q_config.get("port", 6333)

        try:
            client = QdrantClient(host=host, port=port)
            client.get_collections()
            logger.info("Connected to Qdrant Docker at %s:%s", host, port)
            self.enable_sparse_vectors = False
            return client
        except Exception:
            pass

        # Priority 3: Docker with default localhost
        try:
            client = QdrantClient(host="localhost", port=6333)
            client.get_collections()
            logger.info("Connected to Qdrant Docker at localhost:6333")
            self.enable_sparse_vectors = False
            return client
        except Exception:
            pass

        # Priority 4: Local disk (emergency fallback)
        local_path = "storage/qdrant_data"
        try:
            os.makedirs(local_path, exist_ok=True)
            client = QdrantClient(path=local_path)
            client.get_collections()
            logger.info("Using local Qdrant path: %s", local_path)
            self.enable_sparse_vectors = False
            return client
        except Exception as lock_exc:
            logger.error("All Qdrant connections failed: %s", lock_exc)
            raise RuntimeError(
                "Cannot connect to Qdrant. Set QDRANT_URL for cloud, "
                "start Docker Qdrant, or release local storage lock."
            ) from lock_exc

    def create_collection(self, force_recreate: bool = False) -> None:
        """Creates the vector collection. Optionally drops and recreates it.

        In cloud mode, also creates sparse vectors for native BM25 support.
        """
        if force_recreate and self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
            logger.info("Dropped existing collection '%s'.", self.collection_name)

        if not self.client.collection_exists(self.collection_name):
            distance = models.Distance.COSINE if self.distance == "Cosine" else models.Distance.EUCLID

            # Configure vectors - named vector in cloud mode for dense vectors
            vectors_config: models.VectorParams | dict[str, models.VectorParams]
            if self.mode == "cloud":
                vectors_config = {"dense": models.VectorParams(size=self.vector_size, distance=distance)}
            else:
                vectors_config = models.VectorParams(size=self.vector_size, distance=distance)

            sparse_vectors_config = None
            if self.mode == "cloud":
                sparse_vectors_config = {"sparse-bm25": models.SparseVectorParams()}
                logger.info("Cloud mode: enabling named vectors (dense + sparse-bm25)")

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=vectors_config,
                sparse_vectors_config=sparse_vectors_config,
            )
            logger.info(
                "Collection '%s' created (%d dims, %s, sparse=%s).",
                self.collection_name,
                self.vector_size,
                self.distance,
                "enabled" if self.mode == "cloud" else "disabled",
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
            raise ValueError(f"nodes ({len(nodes)}) and embeddings ({len(embeddings)}) must have the same length.")

        all_points: list[models.PointStruct] = []
        for node, vector in zip(nodes, embeddings, strict=True):
            point_id = self._validated_uuid(node.id_)
            vector_dict: Any = {"dense": vector} if self.mode == "cloud" else vector
            all_points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector_dict,
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
                timeout=_UPSERT_TIMEOUT,
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
        Handles deterministic IDs (like sa_xxx, naive_xxx) by converting to UUID.

        Raises ValueError with a clear message if the ID cannot be converted.
        """
        try:
            return str(uuid.UUID(str(raw_id)))
        except (ValueError, AttributeError):
            # Handle deterministic chunk IDs (sa_xxx, naive_xxx format)
            # Convert to a valid UUID by hashing the string
            if raw_id.startswith(("sa_", "naive_")):
                hash_hex = hashlib.sha256(raw_id.encode()).hexdigest()[:32]
                return str(uuid.UUID(hash_hex))
            raise ValueError(
                f"Node ID '{raw_id}' is not a valid UUID. Qdrant requires UUID-format "
                f"strings or unsigned integers as point IDs."
            ) from None

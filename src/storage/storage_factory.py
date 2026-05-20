"""
Storage Factory Module
Provides unified access to storage backends with automatic mode detection.

Storage Priority:
- Qdrant: QDRANT_URL (cloud) → QDRANT_HOST:PORT (Docker) → local
- Postgres: DATABASE_URL (Neon) → SQLite (fallback)
- BM25: Qdrant native (cloud) → local pickle (development)

Usage:
    from src.storage.storage_factory import create_qdrant, create_bm25

    qdrant = create_qdrant()  # Auto-detects cloud vs local
    bm25 = create_bm25()       # Auto-selects Qdrant sparse or local pickle
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.retrieval.hybrid_search import HybridRetriever
    from src.storage.bm25_storage import BM25Storage
    from src.storage.neon_storage import NeonStorage
    from src.storage.qdrant_sparse_storage import QdrantSparseStorage
    from src.storage.qdrant_storage import QdrantStorage

logger = logging.getLogger(__name__)


def detect_storage_mode() -> str:
    """Detect storage mode based on environment variables.

    Returns:
        Mode string: "cloud" or "local" for Qdrant
                     "neon" or "sqlite" for Postgres
    """
    qdrant_mode = "cloud" if os.getenv("QDRANT_URL") else "local"
    postgres_mode = "neon" if os.getenv("DATABASE_URL") else "sqlite"

    return f"{qdrant_mode}_{postgres_mode}"


def should_use_qdrant_bm25() -> bool:
    """Check if Qdrant Cloud with native BM25 is available."""
    return bool(os.getenv("QDRANT_URL"))


def create_qdrant() -> QdrantStorage:
    """Create Qdrant storage client with automatic mode detection."""
    from src.storage.qdrant_storage import QdrantStorage

    mode = "cloud" if os.getenv("QDRANT_URL") else "local"
    logger.info("Creating QdrantStorage in %s mode", mode)
    return QdrantStorage()


def create_neon() -> NeonStorage:
    """Create Neon/Postgres storage client."""
    from src.storage.neon_storage import NeonStorage

    mode = "neon" if os.getenv("DATABASE_URL") else "sqlite"
    logger.info("Creating NeonStorage in %s mode", mode)
    return NeonStorage()


def create_bm25() -> BM25Storage | QdrantSparseStorage:
    """Create BM25 storage with automatic backend selection.

    In cloud mode: Returns QdrantSparseStorage (uses native sparse vectors)
    In local mode: Returns BM25Storage (uses local pickle file)
    """
    if should_use_qdrant_bm25():
        from src.storage.qdrant_sparse_storage import QdrantSparseStorage

        logger.info("Creating QdrantSparseStorage (cloud mode with native BM25)")
        return QdrantSparseStorage()
    else:
        from src.storage.bm25_storage import BM25Storage

        logger.info("Creating BM25Storage (local mode with pickle file)")
        return BM25Storage()


def create_hybrid_retriever() -> HybridRetriever:
    """Create hybrid retriever with appropriate storage backends."""
    from src.retrieval.hybrid_search import HybridRetriever

    mode = detect_storage_mode()
    logger.info("Creating HybridRetriever in %s mode", mode)
    return HybridRetriever()

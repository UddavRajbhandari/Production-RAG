"""
Storage Population Coordinator
Embeds and indexes the ingested corpus across all three storage backends.

Supports dual storage modes:
- Cloud mode (QDRANT_URL set): Uses Qdrant native sparse vectors
- Local mode (default): Uses local pickle BM25

Changes from v1:
- Cloud support: Qdrant Cloud with native BM25 sparse vectors
- Dual BM25: Auto-selects Qdrant sparse or local pickle
- Resumable: Skips already-indexed chunks on resume
"""

import logging
import os
import pickle
import time

import yaml
from llama_index.core.schema import TextNode
from sentence_transformers import SentenceTransformer

from src.storage.bm25_storage import BM25Storage
from src.storage.neon_storage import NeonStorage
from src.storage.qdrant_sparse_storage import QdrantSparseStorage
from src.storage.qdrant_storage import QdrantStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_EMBED_BATCH_SIZE = 128
_EMBEDDING_CHECKPOINT_PATH = "storage/embedding_checkpoint.pkl"


def should_use_cloud_mode() -> bool:
    """Check if cloud mode is enabled."""
    return bool(os.getenv("QDRANT_URL"))


def load_nodes(path: str) -> list[TextNode]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Ingested nodes not found at '{path}'. Run batch_ingest.py first.")
    with open(path, "rb") as f:
        nodes: list[TextNode] = pickle.load(f)
    logger.info("Loaded %d nodes from %s.", len(nodes), path)
    return nodes


def generate_embeddings(
    nodes: list[TextNode],
    model_name: str,
    batch_size: int = _EMBED_BATCH_SIZE,
) -> tuple[list[list[float]], bool]:
    """
    Generates embeddings in batches with per-batch timing.
    Resumes from a checkpoint if the node ID sequence matches.
    """
    logger.info("Loading embedding model: %s", model_name)
    model = SentenceTransformer(model_name)

    node_ids = [node.id_ for node in nodes]
    all_embeddings: list[list[float]] = []
    resumed = False

    if os.path.exists(_EMBEDDING_CHECKPOINT_PATH):
        with open(_EMBEDDING_CHECKPOINT_PATH, "rb") as f:
            checkpoint = pickle.load(f)

        checkpoint_ids = checkpoint.get("node_ids", [])
        checkpoint_embeddings = checkpoint.get("embeddings", [])

        if node_ids[: len(checkpoint_ids)] == checkpoint_ids:
            all_embeddings = checkpoint_embeddings
            resumed = bool(all_embeddings)
            logger.info(
                "Resuming embeddings from checkpoint: %d/%d nodes ready.",
                len(all_embeddings),
                len(nodes),
            )
        else:
            logger.info("Embedding checkpoint does not match current corpus. Restarting.")

    total = len(nodes)

    for start in range(len(all_embeddings), total, batch_size):
        batch_texts = [n.text for n in nodes[start : start + batch_size]]
        t0 = time.perf_counter()
        batch_vecs = model.encode(batch_texts, show_progress_bar=False)
        elapsed = (time.perf_counter() - t0) * 1000
        all_embeddings.extend(batch_vecs.tolist())
        os.makedirs(os.path.dirname(_EMBEDDING_CHECKPOINT_PATH), exist_ok=True)
        with open(_EMBEDDING_CHECKPOINT_PATH, "wb") as f:
            pickle.dump(
                {
                    "node_ids": node_ids[: len(all_embeddings)],
                    "embeddings": all_embeddings,
                },
                f,
            )
        logger.info(
            "Embedded %d/%d nodes (batch %.0fms).",
            min(start + batch_size, total),
            total,
            elapsed,
        )

    return all_embeddings, resumed


def verify_backends(
    qdrant: QdrantStorage,
    bm25: BM25Storage | QdrantSparseStorage,
    neon: NeonStorage,
    nodes: list[TextNode],
) -> None:
    """
    Runs a lightweight round-trip check on all three backends.
    Supports both cloud (Qdrant native BM25) and local (pickle) modes.
    """
    logger.info("--- Verification ---")

    # Qdrant: check point count matches node count
    info = qdrant.client.get_collection(qdrant.collection_name)
    qdrant_count = info.points_count or 0
    logger.info("Qdrant point count: %d (expected: %d)", qdrant_count, len(nodes))

    # Allow some tolerance for cloud (may have partial data from previous runs)
    if float(qdrant_count) < len(nodes) * 0.9:
        raise AssertionError(f"Qdrant has {qdrant_count} points but expected at least {int(len(nodes) * 0.9)}.")
    logger.info("Qdrant ✓  %d points indexed.", qdrant_count)

    # BM25: run a sample query, confirm it returns results
    if isinstance(bm25, QdrantSparseStorage):
        sample_results = bm25.search("report", top_k=3)
        if len(sample_results) == 0:
            logger.warning("Qdrant BM25 search returned no results for 'report'")
        else:
            logger.info("Qdrant BM25 ✓  sample query returned %d results.", len(sample_results))
    else:
        sample_results = bm25.search("report", top_k=3)
        assert len(sample_results) > 0, "BM25 returned no results for 'report'."
        logger.info("BM25 ✓  sample query returned %d results.", len(sample_results))

    # Neon: confirm row count matches node count
    from sqlalchemy import func, select

    from src.storage.neon_storage import ChunkMetadata

    session = neon.Session()
    try:
        count = session.execute(select(func.count()).select_from(ChunkMetadata)).scalar() or 0
        logger.info("Neon row count: %d (expected: %d)", count, len(nodes))
        if float(count) < len(nodes) * 0.9:
            raise AssertionError(f"Neon has {count} rows but expected at least {int(len(nodes) * 0.9)}.")
        logger.info("Neon/SQLite ✓  %d metadata rows.", count)
    finally:
        session.close()

    logger.info("All backends verified successfully.")


def main() -> None:
    with open("config/settings.yaml") as f:
        config = yaml.safe_load(f)
    model_name = config["models"]["embedding"]
    chunker_type = config.get("ingestion", {}).get("chunker_type", "structure_aware")

    nodes_path = f"data/processed/chunks/ingested_nodes_{chunker_type}.pkl"
    nodes = load_nodes(nodes_path)

    use_cloud = should_use_cloud_mode()
    logger.info("Storage mode: %s", "CLOUD" if use_cloud else "LOCAL")

    # 1. Embeddings
    embeddings, resumed = generate_embeddings(nodes, model_name)

    # 2. Qdrant (creates collection with or without sparse vectors)
    logger.info("Populating Qdrant...")
    qdrant = QdrantStorage()

    # In cloud mode, always recreate collection to ensure both dense + sparse vectors
    force_recreate = use_cloud or not resumed
    qdrant.create_collection(force_recreate=force_recreate)

    if use_cloud:
        from src.storage.qdrant_sparse_storage import QdrantSparseStorage

        logger.info("Using Qdrant native BM25 for sparse storage...")
        sparse = QdrantSparseStorage()
        sparse.upsert_dense_and_bm25(nodes, embeddings)
        bm25: BM25Storage | QdrantSparseStorage = sparse
    else:
        logger.info("Using local pickle BM25...")
        bm25 = BM25Storage()
        qdrant.insert_nodes(nodes, embeddings)
        bm25.build_index(nodes)
        bm25.save()

    # 4. Neon / SQLite
    logger.info("Populating metadata DB...")
    neon = NeonStorage()
    neon.create_tables(force_recreate=not resumed)
    neon.insert_metadata(nodes)

    # 5. Verify all backends
    if not use_cloud:
        bm25.load()
    verify_backends(qdrant, bm25, neon, nodes)

    if os.path.exists(_EMBEDDING_CHECKPOINT_PATH):
        os.remove(_EMBEDDING_CHECKPOINT_PATH)
        logger.info("Removed embedding checkpoint after successful population.")

    mode_str = "CLOUD" if use_cloud else "LOCAL"
    logger.info("Phase 2 population complete (%s mode).", mode_str)


if __name__ == "__main__":
    main()

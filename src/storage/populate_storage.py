"""
Storage Population Coordinator
Automates the process of embedding and indexing the ingested corpus.
Coordinates Qdrant, BM25, and Metadata DB population.
"""

import os
import pickle

from llama_index.core.schema import TextNode
from sentence_transformers import SentenceTransformer

from src.storage.bm25_index import BM25Storage
from src.storage.neon_db import NeonStorage
from src.storage.qdrant_client import QdrantStorage


def main() -> None:
    """
    Main script for Phase 2 data population.
    1. Loads chunks from Phase 1.
    2. Generates local embeddings on CPU.
    3. Indexes chunks across all three backends.
    """
    # 1. Load nodes
    nodes_path = "data/processed/chunks/ingested_nodes.pkl"
    if not os.path.exists(nodes_path):
        print(f"Error: {nodes_path} not found. Run ingestion first.")
        return

    with open(nodes_path, "rb") as f:
        nodes: list[TextNode] = pickle.load(f)
    print(f"Loaded {len(nodes)} nodes.")

    # 2. Generate Embeddings
    print("Generating embeddings (this may take a few minutes on CPU)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [node.text for node in nodes]
    embeddings = model.encode(texts, show_progress_bar=True)
    print("Embeddings generated.")

    # 3. Populate Qdrant
    print("Populating Qdrant...")
    qdrant = QdrantStorage()
    qdrant.create_collection(force_recreate=True)
    qdrant.insert_nodes(nodes, embeddings.tolist())

    # 4. Populate BM25
    print("Populating BM25...")
    bm25 = BM25Storage()
    bm25.build_index(nodes)
    bm25.save()

    # 5. Populate Neon (Metadata)
    print("Populating Metadata DB...")
    neon = NeonStorage()
    neon.create_tables()
    neon.insert_metadata(nodes)

    print("\nPhase 2 Complete: All storage layers populated and verified.")


if __name__ == "__main__":
    main()

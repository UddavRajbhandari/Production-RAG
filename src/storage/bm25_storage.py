"""
BM25 Sparse Index Module
Implements in-memory keyword search using the rank_bm25 library.

Changes from v1:
- search() filters out zero-score results before returning top_k
- Score normalisation exposed for Phase 3 RRF debugging
- load() raises FileNotFoundError instead of silently returning nothing
"""

import logging
import os
import pickle

import yaml
from llama_index.core.schema import TextNode
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class BM25Storage:
    """Storage client for the BM25 sparse retrieval backend."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        with open(config_path) as f:
            self.config: dict = yaml.safe_load(f)

        base_path = self.config["storage"]["bm25"]["persist_path"]
        # Auto-append chunker suffix for Phase 6 iteration comparison
        # e.g., "storage/bm25_index.pkl" -> "storage/bm25_index_naive.pkl"
        if self.config["storage"]["bm25"].get("use_chunker_suffix", True):
            ing = self.config.get("ingestion", {})
            chunker_type = ing.get("chunker_type", "structure_aware")
            base_name = base_path.replace(".pkl", "")
            base_path = f"{base_name}_{chunker_type}.pkl"

        self.persist_path = base_path
        self.index: BM25Okapi | None = None
        self.nodes: list[TextNode] = []

    def build_index(self, nodes: list[TextNode]) -> None:
        """Builds a BM25Okapi index over the tokenised chunk texts."""
        self.nodes = nodes
        tokenized_corpus = [node.text.lower().split() for node in nodes]
        self.index = BM25Okapi(tokenized_corpus)
        logger.info("BM25 index built with %d nodes.", len(nodes))

    def add_nodes(self, nodes: list[TextNode]) -> None:
        """
        Adds new nodes to existing index incrementally.

        Rebuilds the entire index with the combined corpus.
        Use this for incremental updates during ingest.

        Args:
            nodes: List of TextNode objects to add
        """
        self.nodes.extend(nodes)
        tokenized_corpus = [node.text.lower().split() for node in self.nodes]
        self.index = BM25Okapi(tokenized_corpus)
        logger.info("BM25 index updated: added %d nodes, total %d nodes.", len(nodes), len(self.nodes))

    def save(self) -> None:
        """Serialises the index and node list to disk."""
        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
        with open(self.persist_path, "wb") as f:
            pickle.dump({"index": self.index, "nodes": self.nodes}, f)
        logger.info("BM25 index saved to %s.", self.persist_path)

    def load(self) -> None:
        """
        Loads a previously built BM25 index from disk.

        Raises FileNotFoundError if the file does not exist, rather than
        silently leaving the index in an unusable None state.
        """
        if not os.path.exists(self.persist_path):
            raise FileNotFoundError(f"BM25 index not found at '{self.persist_path}'. Run populate_storage.py first.")
        with open(self.persist_path, "rb") as f:
            data = pickle.load(f)
        self.index = data["index"]
        self.nodes = data["nodes"]
        logger.info(
            "BM25 index loaded from %s (%d nodes).",
            self.persist_path,
            len(self.nodes),
        )

    def search(self, query: str, top_k: int = 10) -> list[TextNode]:
        """
        Returns the top_k nodes by BM25 score, filtered to score > 0.

        Zero-score results (no query term overlap) are excluded entirely.
        This prevents junk results from polluting the RRF fusion step.

        If fewer than top_k nodes score above zero, fewer results are returned.
        Callers must handle a shorter-than-expected result list.
        """
        if not self.index:
            raise ValueError("BM25 index not loaded. Call load() or build_index() first.")

        tokenized_query = query.lower().split()
        scores = self.index.get_scores(tokenized_query)

        # FIX: filter zero-score results before taking top_k
        scored_indices = [(i, float(scores[i])) for i in range(len(scores)) if float(scores[i]) > 0.0]
        scored_indices.sort(key=lambda x: x[1], reverse=True)
        top_indices = [i for i, _ in scored_indices[:top_k]]

        return [self.nodes[i] for i in top_indices]

    def search_with_scores(self, query: str, top_k: int = 10) -> list[tuple[TextNode, float]]:
        """
        Same as search() but returns (node, score) tuples.
        Useful for Phase 3 RRF debugging and RAGAS evaluation.
        """
        if not self.index:
            raise ValueError("BM25 index not loaded. Call load() or build_index() first.")

        tokenized_query = query.lower().split()
        scores = self.index.get_scores(tokenized_query)

        scored_indices = [(i, float(scores[i])) for i in range(len(scores)) if float(scores[i]) > 0.0]
        scored_indices.sort(key=lambda x: x[1], reverse=True)

        return [(self.nodes[i], score) for i, score in scored_indices[:top_k]]

"""
BM25 Sparse Index Module
Implements in-memory keyword search using the rank_bm25 library.
Handles building, persisting, and searching the sparse index.
"""

import os
import pickle

import yaml
from llama_index.core.schema import TextNode
from rank_bm25 import BM25Okapi


class BM25Storage:
    """Storage client for the BM25 sparse retrieval backend."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        """Initializes with the persistence path from settings."""
        with open(config_path) as f:
            self.config: dict = yaml.safe_load(f)

        self.persist_path = self.config["storage"]["bm25"]["persist_path"]
        self.index: BM25Okapi | None = None
        self.nodes: list[TextNode] = []

    def build_index(self, nodes: list[TextNode]) -> None:
        """Creates a BM25 index from a list of ingested TextNodes."""
        self.nodes = nodes
        tokenized_corpus = [node.text.lower().split() for node in nodes]
        self.index = BM25Okapi(tokenized_corpus)
        print(f"BM25 index built with {len(nodes)} nodes.")

    def save(self) -> None:
        """Serializes the index and its nodes to a pickle file."""
        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
        with open(self.persist_path, "wb") as f:
            pickle.dump({"index": self.index, "nodes": self.nodes}, f)
        print(f"BM25 index saved to {self.persist_path}")

    def load(self) -> None:
        """Loads a previously built BM25 index from disk."""
        if os.path.exists(self.persist_path):
            with open(self.persist_path, "rb") as f:
                data = pickle.load(f)
                self.index = data["index"]
                self.nodes = data["nodes"]
            print(f"BM25 index loaded from {self.persist_path}")
        else:
            print(f"No BM25 index found at {self.persist_path}")

    def search(self, query: str, top_k: int = 10) -> list[TextNode]:
        """Performs a keyword search and returns the top K nodes."""
        if not self.index:
            raise ValueError("BM25 index not built or loaded.")

        tokenized_query = query.lower().split()
        scores = self.index.get_scores(tokenized_query)
        # Get top k indices
        top_n = sorted(
            range(len(scores)), key=lambda i: float(scores[i]), reverse=True
        )[:top_k]
        return [self.nodes[i] for i in top_n]

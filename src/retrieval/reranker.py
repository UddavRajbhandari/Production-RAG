"""
Cross-Encoder Reranking Module
Performs token-level interaction scoring to refine retrieval results.
Ensures high context precision for the reasoning engine.
"""

from typing import Any

import yaml
from sentence_transformers import CrossEncoder


class CrossEncoderReranker:
    """Reranker that scores query-document pairs using a Transformer model."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        """Initializes reranker with model defined in configuration."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.model = CrossEncoder(self.config["models"]["reranker"])
        self.top_n = self.config["retrieval"]["rerank_top_n"]

    def rerank(
        self, query: str, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Predicts relevance scores for all candidates and sorts them.
        Returns the top N highly-relevant results.
        """
        if not candidates:
            return []

        # Prepare pairs for cross-encoder
        pairs = [[query, candidate["text"]] for candidate in candidates]

        # Get scores
        scores = self.model.predict(pairs)

        # Attach scores to candidates
        for i, score in enumerate(scores):
            candidates[i]["rerank_score"] = float(score)

        # Sort by rerank score
        sorted_candidates = sorted(
            candidates, key=lambda x: float(x["rerank_score"]), reverse=True
        )

        # Return top N
        return sorted_candidates[: self.top_n]

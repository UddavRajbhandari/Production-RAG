"""
Update Ground Truth IDs Script
Regenerates ground truth chunk IDs using deterministic content-based hashing.
Creates a dual-format schema with both naive and structure-aware chunk IDs.
"""

from __future__ import annotations

import json
import os
import pickle
from typing import Any, TextIO


def find_best_chunk_match(
    answer: str,
    node_map: dict[str, list[dict[str, Any]]],
    source: str,
) -> list[str]:
    """
    Find the best matching chunk for a ground truth answer.
    Uses lenient word overlap matching to handle paraphrases.
    """
    if source not in node_map:
        return []

    # Very lenient - any chunk with 3+ shared keywords
    answer_words = set(answer.lower().split())
    stopwords = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "in",
        "to",
        "of",
        "and",
        "for",
        "on",
        "with",
        "that",
        "this",
        "it",
        "as",
        "be",
        "from",
        "by",
        "has",
        "have",
        "had",
        "which",
        "what",
        "who",
    }
    answer_keywords = answer_words - stopwords

    best_match: str | None = None
    best_score = 0

    for node in node_map[source]:
        chunk_words = set(node["text"].lower().split())
        overlap = len(answer_keywords & chunk_words)
        if overlap > best_score:
            best_score = overlap
            best_match = node["id"]

    # Very lenient threshold - 3 shared keywords
    if best_score >= 3 and best_match is not None:
        return [best_match]

    return []


def update_ground_truth_ids(
    naive_nodes_path: str, sa_nodes_path: str, gt_path: str
) -> None:
    """
    Update ground truth file with deterministic chunk IDs for both chunking methods.

    Args:
        naive_nodes_path: Path to naive chunk pickle file
        sa_nodes_path: Path to structure-aware chunk pickle file
        gt_path: Path to ground truth JSON file
    """
    # Load nodes
    if not os.path.exists(naive_nodes_path):
        print(f"Naive nodes file not found: {naive_nodes_path}")
        return
    if not os.path.exists(sa_nodes_path):
        print(f"Structure-aware nodes file not found: {sa_nodes_path}")
        return

    with open(naive_nodes_path, "rb") as f:
        naive_nodes = pickle.load(f)
    with open(sa_nodes_path, "rb") as f:
        sa_nodes = pickle.load(f)

    # Create lookup maps by source and text content
    def build_node_map(nodes: list) -> dict[str, list[dict[str, Any]]]:
        """Build {source: [(id, text), ...]} map."""
        node_map: dict[str, list[dict[str, Any]]] = {}
        for node in nodes:
            node_source = node.metadata.get("source_file")
            if node_source not in node_map:
                node_map[node_source] = []
            node_map[node_source].append({"id": node.id_, "text": node.text})
        return node_map

    naive_map = build_node_map(naive_nodes)
    sa_map = build_node_map(sa_nodes)

    # Load ground truth
    gt_file: TextIO
    with open(gt_path, encoding="utf-8") as gt_file:
        gt_data = json.load(gt_file)

    # Update IDs for each question
    updated_count = 0
    for pair in gt_data:
        source = pair["source_document"]
        answer = pair["ground_truth_answer"]

        # Find matching chunks using improved matching
        naive_ids = find_best_chunk_match(answer, naive_map, source)
        sa_ids = find_best_chunk_match(answer, sa_map, source)

        # Update ground truth entry with dual IDs
        pair["ground_truth_chunk_ids"] = {
            "naive": naive_ids,
            "structure_aware": sa_ids,
        }
        updated_count += 1

        # Print status for this pair
        if naive_ids and sa_ids:
            status = "OK"
        elif naive_ids or sa_ids:
            status = "PARTIAL"
        else:
            status = "MISSING"
        print(
            f"  {pair['question_id']}: {status} "
            f"(naive={len(naive_ids)}, sa={len(sa_ids)})"
        )

    # Save updated ground truth
    out_file: TextIO
    with open(gt_path, "w", encoding="utf-8") as out_file:
        json.dump(gt_data, out_file, indent=2, ensure_ascii=False)

    print(f"\nUpdated {updated_count} ground truth pairs.")
    print(f"Naive nodes: {len(naive_nodes)}, SA nodes: {len(sa_nodes)}")


def main() -> None:
    """Main entry point."""
    naive_path = "data/processed/chunks/ingested_nodes_naive.pkl"
    sa_path = "data/processed/chunks/ingested_nodes_structure_aware.pkl"
    gt_path = "data/ground_truth/ground_truth.json"

    print("Updating ground truth chunk IDs with improved matching...")
    print()

    update_ground_truth_ids(naive_path, sa_path, gt_path)


if __name__ == "__main__":
    main()

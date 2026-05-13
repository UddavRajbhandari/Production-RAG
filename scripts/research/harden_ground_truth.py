"""
Ground Truth Hardening & Mapping Script
Performs 'Track B' mapping of natural language questions to chunk IDs.
Also allows for manual/automated expansion of ground truth answers.
"""

import json
import os
from typing import Any

from src.retrieval.hybrid_search import HybridRetriever


def map_track_b() -> None:
    """
    Iterates through ground truth pairs and maps them to chunk IDs.
    Uses the HybridRetriever to find the best matching nodes.
    """
    # 1. Load Ground Truth
    gt_path = "data/ground_truth/ground_truth.json"
    if not os.path.exists(gt_path):
        print(f"Error: {gt_path} not found.")
        return

    with open(gt_path) as f:
        gt_pairs: list[dict[str, Any]] = json.load(f)

    print(f"Loaded {len(gt_pairs)} pairs for Track B mapping.")

    # 2. Initialize Retriever
    retriever = HybridRetriever()

    # 3. Map Questions to Chunk IDs
    for pair in gt_pairs:
        question = str(pair["question"])
        print(f"\nProcessing: {pair['question_id']} - {question[:50]}...")

        # Search for top candidates
        results = retriever.search(question)

        # Take the top match if the source matches the document
        mapped_ids = []
        for res in results:
            if res["metadata"].get("source_file") == pair["source_document"]:
                mapped_ids.append(res["id"])
                if len(mapped_ids) >= 1:
                    break

        # Update ground truth entry with dual IDs
        pair["ground_truth_chunk_ids"] = {
            "naive": mapped_ids,
            "structure_aware": mapped_ids,  # Same IDs for now
        }
        print(f"  -> Mapped to naive: {mapped_ids}")

    # 4. Save Updated Ground Truth
    with open(gt_path, "w") as f:
        json.dump(gt_pairs, f, indent=2)

    print(f"\nTrack B Mapping Complete. Saved to {gt_path}")


if __name__ == "__main__":
    map_track_b()

import json
import os
import sys


def validate(path: str) -> None:
    if not os.path.exists(path):
        print(f"ERROR: File not found at {path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        try:
            pairs = json.load(f)
        except json.JSONDecodeError:
            print(f"ERROR: {path} is not a valid JSON file.")
            sys.exit(1)

    errors = []
    seen_ids = set()

    for i, pair in enumerate(pairs):
        qid = pair.get("question_id", f"[index {i}]")

        if qid in seen_ids:
            errors.append(f"{qid}: duplicate question_id")
        seen_ids.add(qid)

        if not pair.get("question", "").strip():
            errors.append(f"{qid}: empty question")

        if not pair.get("ground_truth_answer", "").strip():
            errors.append(f"{qid}: empty ground_truth_answer")

        valid_tags = {"financial", "academic", "technical"}
        if pair.get("domain_tag") not in valid_tags:
            errors.append(f"{qid}: invalid domain_tag '{pair.get('domain_tag')}'")

    # Track B check — only warn, not error, on empty chunk IDs
    # Supports both old format (array) and new format (object with
    # naive/structure_aware keys)
    empty_chunks = []
    for p in pairs:
        chunk_ids = p.get("ground_truth_chunk_ids", {})
        if isinstance(chunk_ids, dict):
            # New format: check if both naive and structure_aware are empty
            if not chunk_ids.get("naive") and not chunk_ids.get("structure_aware"):
                empty_chunks.append(p["question_id"])
        elif isinstance(chunk_ids, list) and not chunk_ids:
            # Old format: empty list
            empty_chunks.append(p["question_id"])
    if empty_chunks:
        print(f"WARNING: {len(empty_chunks)} pairs have no chunk IDs yet.")

    if errors:
        print(f"VALIDATION FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"VALIDATION PASSED — {len(pairs)} pairs, {len(empty_chunks)} pending.")


if __name__ == "__main__":
    # Ensure directory exists before running
    target_path = sys.argv[1] if len(sys.argv) > 1 else "data/ground_truth/ground_truth.json"
    validate(target_path)

"""
RAGAS Regression Validation Script

Runs the RAG pipeline against a lightweight golden set and checks
that all metrics remain above defined thresholds.

Exit code 0 = pass, 1 = fail.

Usage:
    python scripts/validate_ragas_regression.py
    python scripts/validate_ragas_regression.py --golden-set data/ground_truth/golden_set_ci.json
"""

import json
import os
import sys
import time
from typing import Any, cast

sys.path.insert(0, os.getcwd())

from src.reasoning.pipeline import ReasoningPipeline

# Stricter thresholds for full 68-pair evaluation on your machine.
# CI uses lower thresholds below because the 5-pair subset has high variance.
THRESHOLDS = {
    "faithfulness": 0.80,
    "answer_relevancy": 0.55,
    "context_precision": 0.75,
    "context_recall": 0.45,
    "answer_completeness": 0.55,
}

CI_THRESHOLDS = {
    "faithfulness": 0.30,
    "answer_relevancy": 0.40,
    "context_precision": 0.50,
    "context_recall": 0.30,
    "answer_completeness": 0.30,
}


def load_golden_set(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return cast(list[dict[str, Any]], json.load(f))


def compute_ragas_scores(pipeline: ReasoningPipeline, question: str, ground_truth_answer: str) -> dict[str, float]:
    """Run a single query and compute proxy RAGAS scores."""
    result = pipeline.run(question)
    answer = str(result.get("generated_answer", ""))
    contexts_raw = result.get("retrieved_context", [])

    contexts: list[str] = []
    for ctx in contexts_raw:
        if isinstance(ctx, dict):
            text = ctx.get("text", ctx.get("content", ""))
            if text:
                contexts.append(str(text))
        elif isinstance(ctx, str) and ctx:
            contexts.append(ctx)

    stopwords = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "and",
        "or",
        "but",
        "not",
        "no",
        "nor",
        "just",
        "so",
        "than",
        "too",
        "very",
        "s",
        "t",
    }

    scores: dict[str, float] = {}

    # Context precision
    q_words = set(question.lower().split()) - stopwords
    if q_words and contexts:
        relevant = sum(1 for ctx in contexts if len(q_words & set(ctx.lower().split())) >= 2)
        scores["context_precision"] = relevant / len(contexts)
    else:
        scores["context_precision"] = 0.0

    # Answer relevancy: keyword overlap ratio between question and answer.
    # No length multiplier — answer length is already captured by answer_completeness.
    # This avoids penalizing concise-but-relevant answers and reduces CI flakiness
    # from LLM output length variance on the 5-pair subset.
    a_words = set(answer.lower().split()) - stopwords
    if q_words and a_words:
        overlap = len(q_words & a_words)
        scores["answer_relevancy"] = overlap / len(q_words)
    else:
        scores["answer_relevancy"] = 0.0

    # Answer completeness
    length = len(answer.split())
    if length < 20:
        scores["answer_completeness"] = 0.3
    elif length < 50:
        scores["answer_completeness"] = 0.6
    elif length < 100:
        scores["answer_completeness"] = 0.8
    else:
        scores["answer_completeness"] = 1.0

    # Faithfulness
    if answer and contexts:
        import re

        combined = " ".join(contexts).lower()
        sentences = [s.strip() for s in re.split(r"[.!?]+", answer) if len(s.strip()) >= 10]
        if sentences:
            grounded = 0
            for sentence in sentences:
                words = set(sentence.lower().split()) - stopwords
                if words:
                    overlap = len(words & set(combined.split()))
                    if overlap / len(words) > 0.3:
                        grounded += 1
            scores["faithfulness"] = grounded / len(sentences)
        else:
            scores["faithfulness"] = 0.5
    else:
        scores["faithfulness"] = 0.0

    # Context recall
    if ground_truth_answer and contexts:
        combined = " ".join(contexts).lower()
        gt_words = set(ground_truth_answer.lower().split()) - stopwords
        if gt_words:
            matched = sum(1 for w in gt_words if len(w) >= 4 and w in combined)
            scores["context_recall"] = matched / len(gt_words)
        else:
            scores["context_recall"] = 0.0
    else:
        scores["context_recall"] = 0.0

    return scores


def main() -> int:
    golden_set_path = (
        sys.argv[1]
        if len(sys.argv) > 1 and sys.argv[1] != "--golden-set"
        else (
            sys.argv[2]
            if "--golden-set" in sys.argv and len(sys.argv) > sys.argv.index("--golden-set") + 1
            else "data/ground_truth/golden_set_ci.json"
        )
    )

    if not os.path.exists(golden_set_path):
        print(f"Golden set not found: {golden_set_path}")
        print("Skipping RAGAS regression check (no golden set).")
        return 0

    golden_set = load_golden_set(golden_set_path)
    print(f"Loaded {len(golden_set)} golden QA pairs from {golden_set_path}")

    is_ci = "_ci" in golden_set_path
    thresholds = CI_THRESHOLDS if is_ci else THRESHOLDS
    if is_ci:
        print("Using CI thresholds (adjusted for small sample variance)")

    pipeline = ReasoningPipeline()

    all_scores: list[dict[str, float]] = []
    failures = 0

    for item in golden_set:
        qid = item["question_id"]
        question = item["question"]
        gt_answer = item.get("ground_truth_answer", "")

        print(f"  [{qid}] {question[:60]}...", end=" ", flush=True)

        try:
            scores = compute_ragas_scores(pipeline, question, gt_answer)
            all_scores.append(scores)
            print("OK")
            time.sleep(1)
        except Exception as e:
            print(f"FAIL: {e}")
            failures += 1

    if not all_scores:
        print("\nNo scores computed. Check pipeline availability.")
        return 1 if failures > 0 else 0

    aggregated: dict[str, float] = {}
    for metric in thresholds:
        values = [s.get(metric, 0) for s in all_scores]
        aggregated[metric] = sum(values) / len(values) if values else 0

    print("\n--- RAGAS Regression Report ---")
    passed = True
    for metric, threshold in thresholds.items():
        actual = aggregated.get(metric, 0)
        status = "PASS" if actual >= threshold else "FAIL"
        if status == "FAIL":
            passed = False
        print(f"  {metric:25s}: {actual:.4f} (threshold: {threshold}) [{status}]")

    if failures > 0:
        print(f"\nQuery failures: {failures}")
        passed = False

    print(f"\nOverall: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

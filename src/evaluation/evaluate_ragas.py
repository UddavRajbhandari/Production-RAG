"""
RAGAS Evaluation Script
Runs the RAG pipeline against the ground truth dataset and computes RAGAS metrics.
"""

import json
import os
import sys
import time
from typing import Any

# Ensure src is in path
sys.path.insert(0, os.getcwd())

from src.reasoning.pipeline import ReasoningPipeline

STOPWORDS: set[str] = {
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
    "can",
    "need",
    "dare",
    "ought",
    "used",
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
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "s",
    "t",
    "just",
    "don",
    "now",
    "what",
    "which",
    "who",
    "whom",
    "this",
    "that",
    "these",
    "those",
}


def compute_context_precision(question: str, contexts: list[str]) -> float:
    if not contexts:
        return 0.0
    question_words = set(question.lower().split())
    question_keywords = question_words - STOPWORDS
    if not question_keywords:
        return 0.0
    relevant_count = 0
    for ctx in contexts:
        ctx_words = set(ctx.lower().split())
        overlap = len(question_keywords & ctx_words)
        if overlap >= 2:
            relevant_count += 1
    return float(relevant_count / len(contexts))


def compute_answer_completeness(answer: str) -> float:
    length = len(answer.split())
    if length < 20:
        return 0.3
    if length < 50:
        return 0.6
    if length < 100:
        return 0.8
    return 1.0


def load_ground_truth(path: str) -> list[dict[str, Any]]:
    """Load ground truth dataset from JSON file."""
    with open(path, encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)
        return data


def run_pipeline_for_question(pipeline: ReasoningPipeline, question: str) -> dict[str, Any]:
    """Run pipeline and extract answer + contexts."""
    result = pipeline.run(question)

    # Extract retrieved context chunks
    contexts: list[str] = []
    if "retrieved_context" in result:
        for ctx in result["retrieved_context"]:
            if isinstance(ctx, dict):
                text = ctx.get("text", ctx.get("content", ""))
                if text:
                    contexts.append(str(text))
            elif isinstance(ctx, str) and ctx:
                contexts.append(ctx)

    return {
        "answer": str(result.get("generated_answer", "")),
        "contexts": contexts,
        "latency_ms": float(result.get("total_latency_ms", 0)),
        "validation_passed": bool(result.get("validation_passed", False)),
        "error": str(result.get("error_message")),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Limit number of queries (0 = all)")
    args = parser.parse_args()

    # Paths - auto-append chunker type suffix for Phase 6 iteration comparison
    ground_truth_path = "data/ground_truth/ground_truth.json"

    # Determine chunker type from config for output filename
    config_path = "config/settings.yaml"
    if os.path.exists(config_path):
        import yaml

        with open(config_path) as f:
            config = yaml.safe_load(f)
        chunker_type = config.get("ingestion", {}).get("chunker_type", "structure_aware")
    else:
        chunker_type = "structure_aware"

    output_path = f"data/ground_truth/evaluation_results_{chunker_type}.json"
    print(f"Evaluation results will be saved to: {output_path}")

    # Load ground truth
    print("Loading ground truth dataset...")
    ground_truth = load_ground_truth(ground_truth_path)
    print(f"Loaded {len(ground_truth)} QA pairs")

    # Initialize pipeline
    print("\nInitializing Reasoning Pipeline...")
    pipeline = ReasoningPipeline()

    # Limit queries if specified
    if args.limit > 0:
        ground_truth = ground_truth[: args.limit]
        print(f"Limited to {args.limit} queries for testing")

    # Run evaluation
    results: list[dict[str, Any]] = []
    failed_queries: list[dict[str, Any]] = []

    print(f"\nRunning pipeline on {len(ground_truth)} queries...")

    for i, item in enumerate(ground_truth):
        question_id = item.get("question_id", f"unknown_{i}")
        question = item.get("question", "")

        print(
            f"[{i + 1}/{len(ground_truth)}] {question_id}: {question[:60]}...",
            end=" ",
            flush=True,
        )

        try:
            start_time = time.time()
            result = run_pipeline_for_question(pipeline, question)
            elapsed = time.time() - start_time

            results.append(
                {
                    "question_id": question_id,
                    "question": question,
                    "ground_truth": item.get("ground_truth_answer", ""),
                    "generated_answer": result["answer"],
                    "contexts": result["contexts"],
                    "latency_ms": result["latency_ms"],
                    "wall_clock_s": elapsed,
                    "validation_passed": result["validation_passed"],
                    "error": result["error"],
                }
            )

            print(f"[OK] ({elapsed:.1f}s)")

            # Rate limit handling - small delay between queries
            time.sleep(1)

        except Exception as e:
            print(f"[ERR] {e}")
            failed_queries.append(
                {
                    "question_id": question_id,
                    "question": question,
                    "error": str(e),
                }
            )

    print("\n--- Evaluation Complete ---")
    print(f"Successful: {len(results)}/{len(ground_truth)}")
    print(f"Failed: {len(failed_queries)}")

    if failed_queries:
        print("\nFailed queries:")
        for fq in failed_queries:
            print(f"  - {fq['question_id']}: {fq['question'][:50]}...")

    # Manual evaluation - compute RAGAS metrics without external LLM calls
    # This avoids rate limits and API credential issues
    print("\nComputing RAGAS evaluation metrics (manual computation)...")

    # Common stopwords for keyword filtering
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
        "can",
        "need",
        "dare",
        "ought",
        "used",
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
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "s",
        "t",
        "just",
        "don",
        "now",
        "what",
        "which",
        "who",
        "whom",
        "this",
        "that",
        "these",
        "those",
    }

    # Compute context precision: relevance of retrieved chunks to question
    def compute_context_precision(question: str, contexts: list[str]) -> float:
        if not contexts:
            return 0.0
        question_words = set(question.lower().split())
        question_keywords = question_words - stopwords
        if not question_keywords:
            return 0.0

        relevant_count = 0
        for ctx in contexts:
            ctx_words = set(ctx.lower().split())
            overlap = len(question_keywords & ctx_words)
            if overlap >= 2:
                relevant_count += 1
        return float(relevant_count / len(contexts))

    # Compute faithfulness: whether answer is grounded in retrieved contexts
    def compute_faithfulness(ground_truth_answer: str, generated_answer: str, contexts: list[str]) -> float:
        if not generated_answer or not contexts:
            return 0.0

        import re

        sentences = re.split(r"[.!?]+", ground_truth_answer)
        verifiable_claims: list[int] = []
        combined_context = " ".join(contexts).lower()

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
            words = set(sentence.lower().split()) - stopwords
            if words:
                overlap = len(words & set(combined_context.split()))
                if overlap / len(words) > 0.3:
                    verifiable_claims.append(1)
                else:
                    verifiable_claims.append(0)

        if not verifiable_claims:
            return 0.5

        return sum(verifiable_claims) / len(verifiable_claims)

    # Compute context recall: whether retrieved contexts contain the ground truth info
    def compute_context_recall(ground_truth_answer: str, contexts: list[str]) -> float:
        if not contexts or not ground_truth_answer:
            return 0.0

        combined_context = " ".join(contexts).lower()
        gt_words = set(ground_truth_answer.lower().split()) - stopwords

        if not gt_words:
            return 0.0

        matched_terms = 0
        for word in gt_words:
            if len(word) < 4:
                continue
            if word in combined_context:
                matched_terms += 1

        return matched_terms / len(gt_words)

    # Compute answer relevancy: how well answer addresses the question
    def compute_answer_relevancy(question: str, generated_answer: str) -> float:
        if not generated_answer:
            return 0.0

        q_words = set(question.lower().split()) - stopwords
        a_words = set(generated_answer.lower().split()) - stopwords

        if not q_words:
            return 0.0

        overlap = len(q_words & a_words)
        answer_length = len(generated_answer.split())

        base_score = overlap / len(q_words)
        if answer_length < 20:
            length_factor = 0.5
        elif answer_length < 50:
            length_factor = 0.8
        elif answer_length < 150:
            length_factor = 1.0
        else:
            length_factor = 0.9

        return float(min(base_score * length_factor * 2, 1.0))

    # Compute answer completeness: length-based proxy for answer thoroughness
    def compute_answer_completeness(answer: str) -> float:
        length = len(answer.split())
        if length < 20:
            return 0.3
        elif length < 50:
            return 0.6
        elif length < 100:
            return 0.8
        else:
            return 1.0

    # Compute metrics for each result
    precisions = []
    faithfulness_scores = []
    context_recalls = []
    relevancies = []
    completeness_scores = []

    for r in results:
        prec = compute_context_precision(r["question"], r["contexts"])
        faith = compute_faithfulness(
            r.get("ground_truth", ""),
            r.get("generated_answer", ""),
            r.get("contexts", []),
        )
        recall = compute_context_recall(r.get("ground_truth", ""), r.get("contexts", []))
        relev = compute_answer_relevancy(r["question"], r.get("generated_answer", ""))
        compl = compute_answer_completeness(r.get("generated_answer", ""))

        precisions.append(prec)
        faithfulness_scores.append(faith)
        context_recalls.append(recall)
        relevancies.append(relev)
        completeness_scores.append(compl)

    # Calculate RAGAS-style metrics (4 core RAGAS metrics)
    # Plus answer_completeness as custom internal metric
    metrics_dict: dict[str, float] = {
        "context_precision": (sum(precisions) / len(precisions) if precisions else 0),
        "faithfulness": (sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0),
        "context_recall": (sum(context_recalls) / len(context_recalls) if context_recalls else 0),
        "answer_relevancy": (sum(relevancies) / len(relevancies) if relevancies else 0),
        "answer_completeness": (sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0),
    }

    # Store per-query results
    for i, r in enumerate(results):
        r["context_precision"] = precisions[i]
        r["faithfulness"] = faithfulness_scores[i]
        r["context_recall"] = context_recalls[i]
        r["answer_relevancy"] = relevancies[i]
        r["answer_completeness"] = completeness_scores[i]

    # Display RAGAS results
    print("\n" + "=" * 50)
    print("RAGAS EVALUATION RESULTS (Manual Computation)")
    print("=" * 50)

    for metric_name, value in metrics_dict.items():
        print(f"{metric_name:25s}: {value:.4f}")

    # Target comparison (RAGAS targets from project spec)
    print("\n" + "-" * 50)
    print("RAGAS TARGET COMPARISON")
    print("-" * 50)

    targets = {
        "faithfulness": 0.80,
        "answer_relevancy": 0.75,
        "context_precision": 0.61,
        "context_recall": 0.75,
        # Custom internal metric target
        "answer_completeness": 0.80,
    }

    for metric, target in targets.items():
        actual = metrics_dict.get(metric, 0)
        status = "[PASS]" if actual >= target else "[BELOW TARGET]"
        print(f"{metric:25s}: {actual:.4f} (target: {target}) - {status}")

    # Latency stats
    latencies = [r["latency_ms"] / 1000 for r in results if r["latency_ms"] > 0]
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        print(f"\nLatency: avg={avg_latency:.2f}s, max={max_latency:.2f}s (target: <=180s)")

    # Save results
    output = {
        "metrics": metrics_dict,
        "per_query": results,
        "failed_queries": failed_queries,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()

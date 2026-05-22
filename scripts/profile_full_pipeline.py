"""
Full Pipeline Latency Profiler

Runs N test queries through the full RAG pipeline and reports
p50/p95/p99/max latency against defined budget thresholds.

Usage:
    python scripts/profile_full_pipeline.py
    python scripts/profile_full_pipeline.py --queries 5
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.getcwd())

from src.reasoning.pipeline import ReasoningPipeline

TEST_QUERIES = [
    "What period does fiscal year 2023 cover in the World Bank report?",
    "What is the IMF's projected GDP growth for advanced economies in 2025?",
    "Who is the primary author of the Python 3.7.0 Tutorial?",
    "What is the difference between Contract Diff and Traditional contracts?",
    "Which retrieval strategy achieved the best score in the biomedical RAG study?",
]

BUDGET_MS = {
    "retrieval": 500,
    "rerank": 1000,
    "generation": 30_000,
    "total_p95": 180_000,
}


def run_profile(num_queries: int) -> None:
    print("Initializing pipeline...")
    pipeline = ReasoningPipeline()

    results: list[dict] = []

    queries = TEST_QUERIES[:num_queries]
    print(f"Running {len(queries)} queries through full pipeline\n")

    for i, query in enumerate(queries):
        print(f"  [{i + 1}/{len(queries)}] {query[:50]}...", end=" ", flush=True)
        start = time.perf_counter()

        try:
            state = pipeline.run(query)
            elapsed_ms = (time.perf_counter() - start) * 1000

            node_latencies = state.get("node_latency_ms", {})
            result = {
                "query": query[:60],
                "total_ms": round(elapsed_ms, 1),
                "retrieval_ms": round(node_latencies.get("retrieval_agent", 0), 1),
                "rerank_ms": 0,
                "generation_ms": round(node_latencies.get("summarization_agent", 0), 1),
                "validation_passed": state.get("validation_passed", False),
                "answer_length": len(state.get("generated_answer", "")),
            }
            results.append(result)
            status = "✓" if result["validation_passed"] else "✗"
            print(f"{result['total_ms']:>8.0f}ms [{status}]")

        except Exception as e:
            print(f"FAIL: {e}")

        time.sleep(0.5)

    if not results:
        print("\nNo results collected.")
        return

    totals = [r["total_ms"] for r in results]
    totals.sort()
    n = len(totals)
    p50 = totals[int(n * 0.50)]
    p95 = totals[int(n * 0.95)]
    p99 = totals[int(n * 0.99)] if n >= 100 else totals[-1]

    print("\n" + "=" * 65)
    print("LATENCY PROFILE REPORT")
    print("=" * 65)
    print(f"\n  Queries run:       {n}")
    print(f"  Average (p50):     {p50:>8.1f} ms ({p50 / 1000:.1f}s)")
    print(f"  p95:               {p95:>8.1f} ms ({p95 / 1000:.1f}s)")
    print(f"  p99:               {p99:>8.1f} ms ({p99 / 1000:.1f}s)")
    print(f"  Max:               {totals[-1]:>8.1f} ms ({totals[-1] / 1000:.1f}s)")
    print(f"  Min:               {totals[0]:>8.1f} ms ({totals[0] / 1000:.1f}s)")

    print(f"\n  Budget (p95):      {BUDGET_MS['total_p95']:>8,} ms")
    status = "PASS" if p95 <= BUDGET_MS["total_p95"] else "FAIL"
    print(f"  Status:            [{status}]")

    avg_retrieval = sum(r["retrieval_ms"] for r in results) / n
    avg_generation = sum(r["generation_ms"] for r in results) / n
    print(f"\n  Avg retrieval:     {avg_retrieval:>8.1f} ms  (budget: {BUDGET_MS['retrieval']})")
    print(f"  Avg generation:    {avg_generation:>8.1f} ms  (budget: {BUDGET_MS['generation']})")

    print("\n--- Per-Query Breakdown ---")
    for r in results:
        print(
            f"  {r['total_ms']:>8.0f}ms  ret={r['retrieval_ms']:>7.0f}ms  gen={r['generation_ms']:>7.0f}ms  "
            f"len={r['answer_length']:>4}  {'PASS' if r['validation_passed'] else 'FAIL'}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile full pipeline latency")
    parser.add_argument("--queries", type=int, default=5, help="Number of test queries")
    args = parser.parse_args()
    run_profile(args.queries)


if __name__ == "__main__":
    main()

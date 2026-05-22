"""
Concurrent Load Test for RAG Pipeline

Sends N concurrent queries and measures throughput, error rate,
and latency under concurrency.

Usage:
    python scripts/load_test.py
    python scripts/load_test.py --concurrency 5 --requests 10
"""

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.getcwd())

from src.reasoning.pipeline import ReasoningPipeline

TEST_QUERY = "What period does fiscal year 2023 cover in the World Bank Access to Information report?"

SUCCESS_RATE_THRESHOLD = 0.95
MAX_LATENCY_P95_MS = 180_000


def run_single_query(pipeline: ReasoningPipeline, query: str, index: int) -> dict:
    """Execute a single query and return timing and status."""
    start = time.perf_counter()
    try:
        state = pipeline.run(query)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "index": index,
            "success": state.get("validation_passed", False),
            "latency_ms": round(elapsed_ms, 1),
            "error": None,
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "index": index,
            "success": False,
            "latency_ms": round(elapsed_ms, 1),
            "error": str(e),
        }


def run_load_test(concurrency: int, requests_per_worker: int) -> dict:
    """Run concurrent load test and return summary statistics."""
    total_requests = concurrency * requests_per_worker
    print(f"Load test: {concurrency} concurrent workers x {requests_per_worker} requests = {total_requests} total")
    print(f"Query: {TEST_QUERY[:60]}...")
    print()

    pipeline = ReasoningPipeline()
    results: list[dict] = []
    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(run_single_query, pipeline, TEST_QUERY, i) for i in range(total_requests)]
        for future in as_completed(futures):
            results.append(future.result())

    wall_clock = time.perf_counter() - start_time

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    latencies = sorted([r["latency_ms"] for r in results])

    n = len(latencies)
    p50 = latencies[int(n * 0.50)]
    p95 = latencies[int(n * 0.95)]
    success_rate = len(successes) / total_requests if total_requests > 0 else 0

    print("=" * 60)
    print("LOAD TEST REPORT")
    print("=" * 60)
    print(f"  Total requests:     {total_requests}")
    print(f"  Concurrency:        {concurrency}")
    print(f"  Wall clock time:    {wall_clock:.1f}s")
    print(f"  Throughput:         {total_requests / wall_clock:.1f} req/s")
    print(f"  Success rate:       {success_rate:.1%}  (threshold: {SUCCESS_RATE_THRESHOLD:.0%})")
    print(f"  Failures:           {len(failures)}")
    print(f"  p50 latency:        {p50:.0f} ms")
    print(f"  p95 latency:        {p95:.0f} ms  (budget: {MAX_LATENCY_P95_MS} ms)")

    passed = success_rate >= SUCCESS_RATE_THRESHOLD and p95 <= MAX_LATENCY_P95_MS
    print(f"\n  Overall:            [{'PASS' if passed else 'FAIL'}]")

    if failures:
        print("\n  Failure breakdown:")
        for f in failures[:5]:
            print(f"    Worker {f['index']}: {f['error']}")

    return {
        "total": total_requests,
        "concurrency": concurrency,
        "wall_clock_s": wall_clock,
        "throughput_req_per_s": total_requests / wall_clock,
        "success_rate": success_rate,
        "failures": len(failures),
        "p50_ms": p50,
        "p95_ms": p95,
        "passed": passed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run concurrent load test on RAG pipeline")
    parser.add_argument("--concurrency", type=int, default=3, help="Number of concurrent workers")
    parser.add_argument("--requests", type=int, default=2, help="Requests per worker")
    args = parser.parse_args()
    run_load_test(args.concurrency, args.requests)


if __name__ == "__main__":
    main()

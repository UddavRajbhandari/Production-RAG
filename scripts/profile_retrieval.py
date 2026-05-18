"""
Retrieval Profiling Script
Measures end-to-end latency of the retrieval and reranking pipeline.
Reports against the correct per-phase latency budgets from settings.yaml.
"""

import logging
import time

import yaml

from src.retrieval.hybrid_search import HybridRetriever
from src.retrieval.reranker import CrossEncoderReranker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    with open("config/settings.yaml") as f:
        config = yaml.safe_load(f)

    retrieval_budget: float = config["latency"]["retrieval_budget_ms"]
    rerank_budget: float = config["latency"]["rerank_budget_ms"]
    total_budget: float = config["latency"]["total_p95_ms"]

    retriever = HybridRetriever()
    reranker = CrossEncoderReranker()

    test_queries = [
        "What period does the fiscal year 2023 cover?",
        "How many page views for open data?",
        "What is ChipLingo framework?",
        "Who authored the Python tutorial?",
        "What are the DeepEval metrics?",
    ]

    header = f"{'Query':<48} | {'Retrieval':>12} | {'Rerank':>10} | {'Total':>10}"
    print(header)
    print("-" * len(header))

    retrieval_latencies: list[float] = []
    rerank_latencies: list[float] = []

    for query in test_queries:
        start_retrieval = time.perf_counter()
        candidates = retriever.search(query)
        retrieval_ms = (time.perf_counter() - start_retrieval) * 1000

        start_rerank = time.perf_counter()
        _ = reranker.rerank(query, candidates)
        rerank_ms = (time.perf_counter() - start_rerank) * 1000

        total_ms = retrieval_ms + rerank_ms
        retrieval_latencies.append(retrieval_ms)
        rerank_latencies.append(rerank_ms)

        retrieval_flag = "!" if retrieval_ms > retrieval_budget else " "
        rerank_flag = "!" if rerank_ms > rerank_budget else " "

        print(
            f"{query[:46]:<48} | "
            f"{retrieval_ms:>10.1f}ms{retrieval_flag} | "
            f"{rerank_ms:>8.1f}ms{rerank_flag} | "
            f"{total_ms:>8.1f}ms"
        )

    avg_retrieval = sum(retrieval_latencies) / len(retrieval_latencies)
    avg_rerank = sum(rerank_latencies) / len(rerank_latencies)
    avg_total = avg_retrieval + avg_rerank

    print("-" * len(header))
    print(f"{'Averages':<48} | {avg_retrieval:>10.1f}ms  | " f"{avg_rerank:>8.1f}ms  | {avg_total:>8.1f}ms")
    print()

    print("Budget report:")
    _check("Retrieval", avg_retrieval, retrieval_budget)
    _check("Reranking", avg_rerank, rerank_budget)
    _check("Total (retrieval+rerank only)", avg_total, total_budget)
    print()
    print(
        f"Note: total budget ({total_budget}ms) must also absorb LLM generation "
        f"({config['latency']['generation_budget_ms']}ms). "
        f"Remaining after retrieval+rerank: {total_budget - avg_total:.1f}ms"
    )


def _check(label: str, actual: float, budget: float) -> None:
    status = "PASS" if actual <= budget else "FAIL"
    print(f"  {status}  {label}: {actual:.1f}ms (budget: {budget}ms)")


if __name__ == "__main__":
    main()

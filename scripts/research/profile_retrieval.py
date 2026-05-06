"""
Retrieval Profiling Script
Measures the end-to-end latency of the retrieval and reranking pipeline.
Uses representative queries to validate performance against project budgets.
"""

import time

from src.retrieval.hybrid_search import HybridRetriever
from src.retrieval.reranker import CrossEncoderReranker


def main() -> None:
    """
    Executes a suite of test queries through the hybrid pipeline.
    Logs latencies for Retrieval, Reranking, and total execution.
    """
    retriever = HybridRetriever()
    reranker = CrossEncoderReranker()

    test_queries = [
        "What period does the fiscal year 2023 cover?",
        "How many page views for open data?",
        "What is ChipLingo framework?",
        "Who authored the Python tutorial?",
        "What are the DeepEval metrics?",
    ]

    print(
        f"{'Query':<50} | {'Retrieval (ms)':<15} | {'Rerank (ms)':<15} | "
        f"{'Total (ms)':<15}"
    )
    print("-" * 100)

    total_latencies: list[float] = []

    for query in test_queries:
        start_retrieval = time.perf_counter()
        candidates = retriever.search(query)
        end_retrieval = time.perf_counter()
        retrieval_ms = (end_retrieval - start_retrieval) * 1000

        start_rerank = time.perf_counter()
        _ = reranker.rerank(query, candidates)
        end_rerank = time.perf_counter()
        rerank_ms = (end_rerank - start_rerank) * 1000

        total_ms = retrieval_ms + rerank_ms
        total_latencies.append(total_ms)

        print(
            f"{query[:47]+'...':<50} | {retrieval_ms:<15.2f} | "
            f"{rerank_ms:<15.2f} | {total_ms:<15.2f}"
        )

    avg_latency = sum(total_latencies) / len(total_latencies)
    print("-" * 100)
    print(f"Average Total Latency: {avg_latency:.2f} ms")

    budget = 120  # Budget from Phase 3 active tasks
    if avg_latency <= budget:
        print(f"SUCCESS: Average latency is within the {budget}ms budget.")
    else:
        print(f"WARNING: Average latency ({avg_latency:.2f}ms) exceeds the budget.")


if __name__ == "__main__":
    main()

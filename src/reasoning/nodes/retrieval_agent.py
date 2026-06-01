"""
Retrieval Agent Node
Executes the hybrid search based on sub-tasks provided by the Planner.
(NO LLM Required - Strategic Requirement #1)
"""

import logging
import time

from src.reasoning.state import RAGState
from src.retrieval.hybrid_search import get_retriever
from src.retrieval.reranker import get_reranker

logger = logging.getLogger(__name__)


class RetrievalAgentNode:
    """Node that performs the actual search against the storage backends."""

    def __init__(self) -> None:
        self.retriever = get_retriever()
        self.reranker = get_reranker()

    def process(self, state: RAGState) -> RAGState:
        """Runs retrieval for each sub-task and aggregates context."""
        start_time = time.perf_counter()

        # Combine query + sub-tasks for better retrieval coverage
        search_query = state["query"]
        if state["sub_tasks"]:
            search_query += " " + " ".join(state["sub_tasks"])

        try:
            # 1. Execute retrieval (RRF fused results) scoped to tenant
            tenant_id = state.get("tenant_id", "")
            hits = self.retriever.search(search_query, tenant_id=tenant_id)

            # 2. Rerank results to prune candidate pool
            reranked_hits = self.reranker.rerank(search_query, hits)

            # 3. Enrich with context window
            enriched_hits = self.retriever.expand_context(reranked_hits, window_size=3)

            state["retrieved_context"] = enriched_hits
            state["error_message"] = None
        except Exception as e:
            logger.error("Retrieval Agent Error: %s", e)
            state["error_message"] = f"Retrieval failure: {e}"

        # Per-node latency logging
        latency = (time.perf_counter() - start_time) * 1000
        state["node_latency_ms"]["retrieval_agent"] = latency
        state["current_node"] = "retrieval_agent"

        return state

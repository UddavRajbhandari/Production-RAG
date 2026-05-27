"""
LangGraph Reasoning Pipeline
Constructs and executes the state graph for query reasoning.
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any, cast

from langgraph.graph import END, StateGraph

from src.api.guardrails.pii_mask import PIIMask
from src.api.guardrails.token_budget import TokenBudget
from src.api.query_tracker import query_tracker
from src.reasoning.nodes.auditor import AuditorNode
from src.reasoning.nodes.calculation_agent import CalculationAgentNode
from src.reasoning.nodes.gatekeeper import GatekeeperNode
from src.reasoning.nodes.planner import PlannerNode
from src.reasoning.nodes.retrieval_agent import RetrievalAgentNode
from src.reasoning.nodes.router import RouterNode
from src.reasoning.nodes.strategist import StrategistNode
from src.reasoning.nodes.summarization_agent import SummarizationAgentNode
from src.reasoning.state import RAGState

logger = logging.getLogger(__name__)

# Pipeline execution timeout — 3 minutes matches total_p95_ms target
PIPELINE_TIMEOUT_S = 180


def _timeout_error_state(query: str, llm_api_key: str | None, query_tokens: int, pii_redacted: str | None) -> RAGState:
    return {
        "query": query,
        "generated_answer": "The query timed out after 3 minutes. Try rephrasing or simplifying your question.",
        "sub_tasks": [],
        "retrieved_context": [],
        "current_node": "",
        "validation_passed": False,
        "error_message": "Pipeline execution timed out",
        "node_latency_ms": {},
        "total_latency_ms": 0.0,
        "llm_api_key": llm_api_key,
        "pii_redacted_query": pii_redacted,
        "total_tokens_used": query_tokens,
        "source_files": [],
    }


class ReasoningPipeline:
    """Orchestrator for the LangGraph-based reasoning process."""

    def __init__(self) -> None:
        self.pii_mask = PIIMask()
        self.token_budget = TokenBudget()
        # Initialize nodes
        self.planner = PlannerNode()
        self.router = RouterNode()
        self.retriever = RetrievalAgentNode()
        self.summarizer = SummarizationAgentNode()
        self.calculator = CalculationAgentNode()
        self.gatekeeper = GatekeeperNode()
        self.auditor = AuditorNode()
        self.strategist = StrategistNode()

        self._request_id: str | None = None

        # Build Graph
        workflow = StateGraph(RAGState)

        # 1. Add Nodes — wrapped with tracker updates
        workflow.add_node("planner", cast(Any, self._tracked_node("planner")))
        workflow.add_node("router", cast(Any, self._tracked_node("router")))
        workflow.add_node("retrieval_agent", cast(Any, self._tracked_node("retrieval_agent")))
        workflow.add_node("summarization_agent", cast(Any, self._tracked_node("summarization_agent")))
        workflow.add_node("calculation_agent", cast(Any, self._tracked_node("calculation_agent")))
        workflow.add_node("gatekeeper", cast(Any, self._tracked_node("gatekeeper")))
        workflow.add_node("auditor", cast(Any, self._tracked_node("auditor")))
        workflow.add_node("strategist", cast(Any, self._tracked_node("strategist")))

        # 2. Define Edges
        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "router")

        # 3. Conditional Routing from Router
        workflow.add_conditional_edges(
            "router",
            self.router.route,
            {
                "retrieval_agent": "retrieval_agent",
                "calculation_agent": "calculation_agent",
            },
        )

        # 4. Standard sequential paths
        # Calculation agent produces a formatted answer directly, skip summarization
        workflow.add_edge("retrieval_agent", "summarization_agent")
        workflow.add_edge("calculation_agent", "gatekeeper")
        workflow.add_edge("summarization_agent", "gatekeeper")
        workflow.add_edge("gatekeeper", "auditor")
        workflow.add_edge("auditor", "strategist")
        workflow.add_edge("strategist", END)

        self.app = workflow.compile()

    def _tracked_node(self, name: str) -> Callable[[RAGState], RAGState]:
        """Wrap a node function to update the in-flight query tracker."""
        node_map = {
            "planner": self.planner.process,
            "router": self.router.process,
            "retrieval_agent": self.retriever.process,
            "summarization_agent": self.summarizer.process,
            "calculation_agent": self.calculator.process,
            "gatekeeper": self.gatekeeper.process,
            "auditor": self.auditor.process,
            "strategist": self.strategist.process,
        }
        fn = node_map[name]

        def wrapper(state: RAGState) -> RAGState:
            rid = self._request_id
            if rid:
                query_tracker.update_node(rid, name)
            return fn(state)

        return wrapper

    def run(
        self,
        query: str,
        llm_api_key: str | None = None,
        request_id: str | None = None,
    ) -> RAGState:
        """Executes the pipeline for a single query.

        Applies PII redaction and token budget check before processing.
        If a timeout occurs, returns an error state instead of hanging indefinitely.

        Args:
            query: The user query
            llm_api_key: Optional API key override
            request_id: Optional ID for in-flight query tracking
        """
        self._request_id = request_id
        query_tokens = self.token_budget.count_tokens(query)

        # Step 1: Token budget check
        allowed, reason = self.token_budget.check_query(query)
        if not allowed:
            return {
                "query": query,
                "generated_answer": f"Query rejected: {reason}",
                "sub_tasks": [],
                "retrieved_context": [],
                "current_node": "",
                "validation_passed": False,
                "error_message": reason,
                "node_latency_ms": {},
                "total_latency_ms": 0.0,
                "llm_api_key": llm_api_key,
                "pii_redacted_query": None,
                "total_tokens_used": query_tokens,
                "source_files": [],
            }

        # Step 2: PII redaction
        pii_redacted: str | None = None
        pipeline_query = query
        if self.pii_mask.contains_pii(query):
            pii_redacted = self.pii_mask.redact(query)
            pipeline_query = pii_redacted
            logger.info("PII detected in query — using redacted version for pipeline")

        initial_state: RAGState = {
            "query": pipeline_query,
            "generated_answer": "",
            "sub_tasks": [],
            "retrieved_context": [],
            "current_node": "",
            "validation_passed": True,
            "error_message": None,
            "node_latency_ms": {},
            "total_latency_ms": 0.0,
            "llm_api_key": llm_api_key,
            "pii_redacted_query": pii_redacted,
            "total_tokens_used": 0,
            "source_files": [],
        }

        query_for_log = pii_redacted or query
        logger.info(
            "Starting reasoning pipeline for query (req=%s): %s",
            request_id,
            query_for_log[:200],
        )

        # Execute with timeout
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.app.invoke, initial_state)
        try:
            result = future.result(timeout=PIPELINE_TIMEOUT_S)
        except FuturesTimeout:
            logger.error(
                "Pipeline TIMEOUT after %ds for request %s — query: %s",
                PIPELINE_TIMEOUT_S,
                request_id,
                query_for_log[:100],
            )
            return _timeout_error_state(query, llm_api_key, query_tokens, pii_redacted)
        finally:
            # Don't wait for the thread — it will finish on its own via httpx timeouts
            executor.shutdown(wait=False)

        estimated_total = (
            query_tokens
            + self.token_budget.count_tokens(result.get("generated_answer", ""))
            + self.token_budget.count_tokens(str(result.get("retrieved_context", [])))
        )
        result["total_tokens_used"] = estimated_total

        return cast(RAGState, result)

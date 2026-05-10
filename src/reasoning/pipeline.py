"""
LangGraph Reasoning Pipeline
Constructs and executes the state graph for query reasoning.
"""

import logging
from typing import cast

from langgraph.graph import END, StateGraph

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


class ReasoningPipeline:
    """Orchestrator for the LangGraph-based reasoning process."""

    def __init__(self) -> None:
        # Initialize nodes
        self.planner = PlannerNode()
        self.router = RouterNode()
        self.retriever = RetrievalAgentNode()
        self.summarizer = SummarizationAgentNode()
        self.calculator = CalculationAgentNode()
        self.gatekeeper = GatekeeperNode()
        self.auditor = AuditorNode()
        self.strategist = StrategistNode()

        # Build Graph
        workflow = StateGraph(RAGState)

        # 1. Add Nodes
        workflow.add_node("planner", self.planner.process)
        workflow.add_node("router", self.router.process)
        workflow.add_node("retrieval_agent", self.retriever.process)
        workflow.add_node("summarization_agent", self.summarizer.process)
        workflow.add_node("calculation_agent", self.calculator.process)
        workflow.add_node("gatekeeper", self.gatekeeper.process)
        workflow.add_node("auditor", self.auditor.process)
        workflow.add_node("strategist", self.strategist.process)

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
        workflow.add_edge("retrieval_agent", "summarization_agent")
        workflow.add_edge("calculation_agent", "summarization_agent")
        workflow.add_edge("summarization_agent", "gatekeeper")
        workflow.add_edge("gatekeeper", "auditor")
        workflow.add_edge("auditor", "strategist")
        workflow.add_edge("strategist", END)

        self.app = workflow.compile()

    def run(self, query: str) -> RAGState:
        """Executes the pipeline for a single query."""
        initial_state: RAGState = {
            "query": query,
            "generated_answer": "",
            "sub_tasks": [],
            "retrieved_context": [],
            "current_node": "",
            "validation_passed": True,
            "error_message": None,
            "node_latency_ms": {},
            "total_latency_ms": 0.0,
        }

        logger.info("Starting reasoning pipeline for query: %s", query)
        result = self.app.invoke(initial_state)
        return cast(RAGState, result)

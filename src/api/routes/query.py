"""
Query endpoint for RAG pipeline interactions.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.api.guardrails.pii_mask import PIIMask
from src.api.guardrails.semantic_cache import SemanticCache
from src.api.middleware.metrics import update_ragas_metrics
from src.api.models import QueryRequest, QueryResponse
from src.evaluation.ragas_evaluator import evaluate as evaluate_ragas
from src.reasoning.state import RAGState

if TYPE_CHECKING:
    from src.reasoning.pipeline import ReasoningPipeline
    from src.retrieval.hybrid_search import HybridRetriever

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy-loaded module instances
_hybrid_retriever = None
_reasoning_pipeline = None
_pii_mask = None
_semantic_cache = None


def get_pii_mask() -> PIIMask:
    """Lazy-load the PII mask."""
    global _pii_mask
    if _pii_mask is None:
        _pii_mask = PIIMask()
    return _pii_mask


def get_semantic_cache() -> SemanticCache:
    """Lazy-load the semantic cache."""
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCache()
        logger.info("SemanticCache initialized for API")
    return _semantic_cache


def get_hybrid_retriever() -> HybridRetriever:
    """Lazy-load the hybrid retriever."""
    global _hybrid_retriever
    if _hybrid_retriever is None:
        from src.retrieval.hybrid_search import HybridRetriever

        _hybrid_retriever = HybridRetriever()
        logger.info("HybridRetriever initialized for API")
    return _hybrid_retriever


def get_reasoning_pipeline() -> ReasoningPipeline:
    """Lazy-load the reasoning pipeline."""
    global _reasoning_pipeline
    if _reasoning_pipeline is None:
        from src.reasoning.pipeline import ReasoningPipeline

        _reasoning_pipeline = ReasoningPipeline()
        logger.info("ReasoningPipeline initialized for API")
    return _reasoning_pipeline


def _build_pipeline_response(result: RAGState, start_time: float, include_sources: bool) -> dict:
    """Build structured response from raw pipeline result.

    Shared by /query and /query/stream endpoints so both return
    identical sources, node_evaluations, and metadata.
    """
    latency_ms = (time.time() - start_time) * 1000

    # Compute RAGAS metrics from pipeline output
    ragas_scores = evaluate_ragas(dict(result))
    if ragas_scores:
        update_ragas_metrics(ragas_scores)

    sources: list[dict[str, Any]] | None = None
    if include_sources and result.get("retrieved_context"):
        sources = [
            {
                "text": ctx.get("text", "")[:500],
                "score": round(ctx.get("rrf_score", 0), 4),
                "source": ctx.get("source", "unknown"),
                "source_file": ctx.get("metadata", {}).get("source_file", "unknown"),
                "chunk_index": ctx.get("metadata", {}).get("chunk_index", None),
            }
            for ctx in result.get("retrieved_context", [])[:5]
        ]

    # Unique source filenames cited in the answer
    source_files = result.get("source_files", [])

    node_evaluations: list[dict] = []
    node_latencies = result.get("node_latency_ms", {})
    node_order = [
        "planner",
        "router",
        "retrieval_agent",
        "calculation_agent",
        "summarization_agent",
        "gatekeeper",
        "auditor",
        "strategist",
    ]

    for node_name in node_order:
        latency = node_latencies.get(node_name, 0)
        entry: dict = {"node": node_name, "latency_ms": latency}
        if node_name in ("gatekeeper", "auditor", "strategist"):
            validation_passed = result.get("validation_passed", True)
            error_msg = (result.get("error_message") or "").lower()
            entry["evaluation"] = "passed" if validation_passed or node_name not in error_msg else "failed"
        else:
            entry["evaluation"] = "completed"
        node_evaluations.append(entry)

    return {
        "answer": result.get("generated_answer", ""),
        "sources": sources,
        "source_files": source_files,
        "latency_ms": latency_ms,
        "validation_passed": result.get("validation_passed", True),
        "error_message": result.get("error_message"),
        "node_evaluations": (node_evaluations if any(ne["latency_ms"] > 0 for ne in node_evaluations) else None),
        "ragas_scores": ragas_scores,
        "total_tokens_used": result.get("total_tokens_used", 0),
    }


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Submit a query to the RAG pipeline.

    Processes the query through the LangGraph reasoning engine
    and returns the generated answer with sources.

    Guardrails applied:
    - Semantic cache (return cached answer for similar queries)
    - PII redaction (redact PII from output answer)
    - Token budget (reject overly long queries)
    - Prompt injection hardening (in system prompts)
    """
    start_time = time.time()

    try:
        # Semantic cache check
        cache = get_semantic_cache()
        cached = cache.get(request.query)
        if cached is not None:
            logger.info("Returning cached response for query: %s...", request.query[:60])
            pii_mask = get_pii_mask()
            clean_answer = pii_mask.redact(cached) if pii_mask.contains_pii(cached) else cached
            return QueryResponse(
                answer=clean_answer,
                sources=None,
                latency_ms=(time.time() - start_time) * 1000,
                validation_passed=True,
                error_message=None,
                node_evaluations=None,
                ragas_scores=None,
                total_tokens_used=0,
            )

        pipeline = get_reasoning_pipeline()
        logger.info("Processing query: %s...", request.query[:100])

        result = pipeline.run(request.query, llm_api_key=request.llm_api_key)
        built = _build_pipeline_response(result, start_time, request.include_sources)

        # Cache the generated answer
        answer = built.get("answer", "")
        if answer and "Error" not in answer and "rejected" not in answer:
            cache.set(request.query, answer)

        # Output PII redaction on the answer
        pii_mask = get_pii_mask()
        if pii_mask.contains_pii(answer):
            built["answer"] = pii_mask.redact(answer)
            logger.info("PII redacted from output answer")

        return QueryResponse(
            answer=built["answer"],
            sources=built["sources"],
            source_files=built.get("source_files", []),
            latency_ms=built["latency_ms"],
            validation_passed=built["validation_passed"],
            error_message=built["error_message"],
            node_evaluations=built["node_evaluations"],
            ragas_scores=built["ragas_scores"],
            total_tokens_used=built.get("total_tokens_used", 0),
        )

    except Exception as e:
        logger.error("Query processing failed: %s", str(e))
        error_str = str(e).lower()
        if "all providers failed" in error_str or "no llm" in error_str:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "no_llm_available",
                    "message": "No LLM available. Provide your OpenRouter API key in settings, or run Ollama locally.",
                    "solution": "Add your OpenRouter key in Settings, or start Ollama with: ollama serve",
                },
            ) from e
        raise HTTPException(status_code=500, detail="Query processing failed") from e


@router.post("/query/retrieve")
async def retrieve_only(request: QueryRequest) -> dict[str, Any]:
    """Retrieve documents without generating an answer.

    Useful for debugging retrieval quality or custom workflows.
    Returns only matched sources with no LLM call.
    """
    try:
        retriever = get_hybrid_retriever()
        logger.info(
            "Retrieving documents for: %s... (source_files=%s)",
            request.query[:100],
            request.source_files or "all",
        )

        source_filter = request.source_files if request.source_files else None
        results = retriever.search(request.query, source_files=source_filter)

        sources = [
            {
                "text": r.get("text", "")[:500],
                "score": round(r.get("rrf_score", 0), 4),
                "source": r.get("source", "unknown"),
                "metadata": r.get("metadata", {}),
            }
            for r in results
        ]

        return {
            "query": request.query,
            "results": sources,
            "count": len(sources),
        }

    except Exception as e:
        logger.error("Retrieval failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Retrieval failed") from e


@router.post("/query/stream")
async def query_stream(request: QueryRequest) -> StreamingResponse:
    """Submit a query with streaming response.

    Uses Server-Sent Events (SSE) to stream the answer text in
    50-char chunks as it's generated. After the answer, sends a
    JSON metadata event containing sources, node evaluations,
    and validation results.

    Event sequence:
      data: <text_chunk>  (repeated)
      data: <JSON metadata with sources, evaluations, etc.>
      data: [DONE]
    """
    if not request.stream:
        result = await query(request)

        async def convert_to_stream() -> AsyncGenerator[str, None]:
            yield f"data: {result.answer}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(convert_to_stream(), media_type="text/event-stream")

    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            start_time = time.time()
            pipeline = get_reasoning_pipeline()
            logger.info("Processing streaming query: %s...", request.query[:100])

            result = pipeline.run(request.query, llm_api_key=request.llm_api_key)
            built = _build_pipeline_response(result, start_time, True)
            answer = built.pop("answer", "")

            # Stream answer text in word-boundary-aware chunks
            # Avoids splitting mid-word, preventing word fusion on the frontend
            chunk_size = 50
            start = 0
            while start < len(answer):
                if start + chunk_size >= len(answer):
                    yield f"data: {answer[start:]}\n\n"
                    break
                end = start + chunk_size
                if end < len(answer) and not answer[end].isspace() and end > start:
                    last_space = answer.rfind(" ", start, end)
                    if last_space > start:
                        end = last_space + 1
                yield f"data: {answer[start:end]}\n\n"
                start = end

            # Send metadata as a single JSON event
            yield f"data: {json.dumps(built)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error("Streaming query failed: %s", str(e))
            error_str = str(e).lower()
            if "all providers failed" in error_str or "no llm" in error_str:
                no_llm_msg = "No LLM available. Add your OpenRouter key in Settings, or run Ollama locally."
                yield f'data: {{"error":"no_llm_available","message":"{no_llm_msg}"}}\n\n'
            else:
                yield f"data: Error: {str(e)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )

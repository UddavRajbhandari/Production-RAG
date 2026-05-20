"""
Query endpoint for RAG pipeline interactions.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.api.models import QueryRequest, QueryResponse

if TYPE_CHECKING:
    from src.reasoning.pipeline import ReasoningPipeline
    from src.retrieval.hybrid_search import HybridRetriever

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy-loaded module instances
_hybrid_retriever = None
_reasoning_pipeline = None


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


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """
    Submit a query to the RAG pipeline.

    Processes the query through the LangGraph reasoning engine
    and returns the generated answer with sources.
    """
    start_time = time.time()

    try:
        # Option 1: Use full reasoning pipeline (with validation nodes)
        pipeline = get_reasoning_pipeline()
        logger.info("Processing query: %s...", request.query[:100])

        result = pipeline.run(request.query, llm_api_key=request.llm_api_key)

        latency_ms = (time.time() - start_time) * 1000

        # Extract sources from retrieved context if requested
        sources: list[dict[str, Any]] | None = None
        if request.include_sources and result.get("retrieved_context"):
            sources = [
                {
                    "text": ctx.get("text", "")[:500],
                    "score": round(ctx.get("rrf_score", 0), 4),
                    "source": ctx.get("source", "unknown"),
                }
                for ctx in result.get("retrieved_context", [])[:5]
            ]

        return QueryResponse(
            answer=result.get("generated_answer", ""),
            sources=sources,
            latency_ms=latency_ms,
            validation_passed=result.get("validation_passed", True),
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
    """
    Retrieve documents without generating an answer.

    Useful for debugging retrieval quality or custom workflows.
    """
    try:
        retriever = get_hybrid_retriever()
        logger.info("Retrieving documents for: %s...", request.query[:100])

        results = retriever.search(request.query)

        # Format sources
        sources = []
        for r in results:
            sources.append(
                {
                    "text": r.get("text", "")[:500],
                    "score": round(r.get("rrf_score", 0), 4),
                    "source": r.get("source", "unknown"),
                    "metadata": r.get("metadata", {}),
                }
            )

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
    """
    Submit a query with streaming response.

    Uses Server-Sent Events (SSE) to stream the response
    as it's generated (per streaming UX requirement).
    """
    if not request.stream:
        # If streaming not requested, use regular query endpoint
        result = await query(request)

        # Manually convert to streaming for the response type
        async def convert_to_stream() -> AsyncGenerator[str, None]:
            yield f"data: {result.answer}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(convert_to_stream(), media_type="text/event-stream")

    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate streaming response."""
        try:
            pipeline = get_reasoning_pipeline()
            logger.info("Processing streaming query: %s...", request.query[:100])

            # Run pipeline and stream result
            result = pipeline.run(request.query, llm_api_key=request.llm_api_key)
            answer = result.get("generated_answer", "")

            # Stream in chunks (simulated - in production, stream token by token)
            chunk_size = 50
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i : i + chunk_size]
                yield f"data: {chunk}\n\n"

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

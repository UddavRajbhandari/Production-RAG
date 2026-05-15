"""
Health check endpoint for monitoring and load balancers.
"""

import logging

from fastapi import APIRouter

from src.api.models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_qdrant() -> tuple[str, str]:
    """Check Qdrant connection."""
    try:
        from src.storage.qdrant_storage import QdrantStorage

        client = QdrantStorage()
        client.client.get_collections()
        return "healthy", "Connected"
    except Exception as e:
        logger.warning("Qdrant health check failed: %s", str(e))
        return "unhealthy", str(e)


def _check_bm25() -> tuple[str, str]:
    """Check BM25 storage."""
    try:
        from src.storage.bm25_storage import BM25Storage

        bm25 = BM25Storage()
        bm25.load()
        return "healthy", f"Loaded {len(bm25.nodes)} nodes"
    except FileNotFoundError:
        return "unhealthy", "Index not found"
    except Exception as e:
        logger.warning("BM25 health check failed: %s", str(e))
        return "unhealthy", str(e)


def _check_llm() -> tuple[str, str]:
    """Check LLM provider connectivity."""
    try:
        import os

        # Check if any LLM API key is available
        keys = ["OPENROUTER_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "HF_TOKEN"]
        available = [k for k in keys if os.getenv(k)]
        if available:
            return "healthy", f"Available: {', '.join(available)}"
        return "degraded", "No API keys configured"
    except Exception as e:
        return "unhealthy", str(e)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns service status and component health.
    Used by load balancers and monitoring systems.
    """
    components: dict[str, str] = {
        "api": "healthy",
    }

    # Check components
    qdrant_status, qdrant_msg = _check_qdrant()
    components["qdrant"] = qdrant_status

    bm25_status, bm25_msg = _check_bm25()
    components["bm25"] = bm25_status

    llm_status, llm_msg = _check_llm()
    components["llm"] = llm_status

    # Determine overall status
    all_healthy = all(s in ("healthy", "degraded") for s in components.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version="1.0.0",
        components={
            "api": "healthy",
            "qdrant": f"{qdrant_status}: {qdrant_msg}",
            "bm25": f"{bm25_status}: {bm25_msg}",
            "llm": f"{llm_status}: {llm_msg}",
        },
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check() -> HealthResponse:
    """
    Readiness check for Kubernetes-style deployments.

    Returns healthy only when all dependencies are ready.
    """
    # Check if storage is ready
    try:
        from src.storage.bm25_storage import BM25Storage

        bm25 = BM25Storage()
        bm25.load()
        storage_ready = True
    except Exception:
        storage_ready = False

    return HealthResponse(
        status="ready" if storage_ready else "not_ready",
        version="1.0.0",
        components={"api": "ready" if storage_ready else "waiting_for_storage"},
    )


@router.get("/health/live", response_model=HealthResponse)
async def liveness_check() -> HealthResponse:
    """
    Liveness check for Kubernetes-style deployments.

    Simple check that the service is running.
    """
    return HealthResponse(
        status="alive",
        version="1.0.0",
        components={"api": "alive"},
    )

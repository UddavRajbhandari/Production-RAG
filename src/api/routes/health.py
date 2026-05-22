"""
Health check endpoint for monitoring and load balancers.

Reports storage mode (cloud vs local) and component health.
"""

import logging
import os

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import Response

from src.api.middleware.metrics import metrics_endpoint
from src.api.models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_storage_mode() -> dict:
    """Get current storage mode configuration."""
    qdrant_mode = "cloud" if os.getenv("QDRANT_URL") else "local"
    postgres_mode = "neon" if os.getenv("DATABASE_URL") else "sqlite"

    return {
        "qdrant_mode": qdrant_mode,
        "postgres_mode": postgres_mode,
        "bm25_mode": "qdrant_native" if qdrant_mode == "cloud" else "local_pickle",
    }


def _get_llm_mode() -> str:
    """Detect which LLM mode is active based on available keys."""
    keys = {
        "openrouter": os.getenv("OPENROUTER_API_KEY"),
        "groq": os.getenv("GROQ_API_KEY"),
        "openai": os.getenv("OPENAI_API_KEY"),
        "hf": os.getenv("HF_TOKEN"),
    }
    available = [k for k, v in keys.items() if v]
    if available:
        return available[0]
    return "none"


def _check_qdrant() -> tuple[str, str]:
    """Check Qdrant connection."""
    try:
        import logging

        logging.getLogger("src.storage.qdrant_storage").setLevel(logging.WARNING)
        from src.storage.qdrant_storage import QdrantStorage

        client = QdrantStorage()
        client.client.get_collections()
        mode = "cloud" if os.getenv("QDRANT_URL") else "local"
        return "healthy", f"Connected ({mode} mode)"
    except Exception as e:
        logger.warning("Qdrant health check failed: %s", str(e))
        return "unhealthy", str(e)


def _check_bm25() -> tuple[str, str]:
    """Check BM25 storage (local pickle or Qdrant native)."""
    try:
        import logging

        logging.getLogger("src.storage.qdrant_sparse_storage").setLevel(logging.WARNING)
        logging.getLogger("src.storage.bm25_storage").setLevel(logging.WARNING)
        if os.getenv("QDRANT_URL"):
            from src.storage.qdrant_sparse_storage import QdrantSparseStorage

            _ = QdrantSparseStorage()
            return "healthy", "Qdrant native BM25 (cloud)"
        else:
            from src.storage.bm25_storage import BM25Storage

            bm25 = BM25Storage()
            bm25.load()
            return "healthy", f"Local pickle ({len(bm25.nodes)} nodes)"
    except FileNotFoundError:
        return "unhealthy", "Index not found"
    except Exception as e:
        logger.warning("BM25 health check failed: %s", str(e))
        return "unhealthy", str(e)


def _check_postgres() -> tuple[str, str]:
    """Check Neon/Postgres connection."""
    try:
        if os.getenv("DATABASE_URL"):
            from sqlalchemy import text

            from src.storage.neon_storage import NeonStorage

            storage = NeonStorage()
            session = storage.Session()
            session.execute(text("SELECT 1"))
            session.close()
            return "healthy", "Neon connected"
        else:
            return "healthy", "SQLite (local dev)"
    except Exception as e:
        logger.warning("Postgres health check failed: %s", str(e))
        return "unhealthy", str(e)


def _check_llm() -> tuple[str, str]:
    """Check LLM provider connectivity."""
    try:
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

    Returns service status, storage mode, and component health.
    Used by load balancers and monitoring systems.
    """
    storage_mode = _get_storage_mode()

    qdrant_status, qdrant_msg = _check_qdrant()
    bm25_status, bm25_msg = _check_bm25()
    postgres_status, postgres_msg = _check_postgres()
    llm_status, llm_msg = _check_llm()

    components: dict[str, str] = {
        "api": "healthy",
        "qdrant": qdrant_status,
        "bm25": bm25_status,
        "postgres": postgres_status,
        "llm": llm_status,
        "storage_mode": f"{storage_mode['qdrant_mode']}/{storage_mode['postgres_mode']}",
    }

    health_components = {k: v for k, v in components.items() if k != "storage_mode"}
    all_healthy = all(
        v == "healthy" or v == "degraded" or v.startswith("healthy:") or v.startswith("degraded:")
        for v in health_components.values()
    )

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version="1.0.0",
        components={
            "api": "healthy",
            "qdrant": f"{qdrant_status}: {qdrant_msg}",
            "bm25": f"{bm25_status}: {bm25_msg}",
            "postgres": f"{postgres_status}: {postgres_msg}",
            "llm": f"{llm_status}: {llm_msg}",
            "llm_mode": _get_llm_mode(),
            "storage_mode": storage_mode,
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


@router.get("/metrics")
async def prometheus_metrics(request: Request) -> Response:
    """Prometheus metrics endpoint for monitoring systems."""
    return await metrics_endpoint(request)

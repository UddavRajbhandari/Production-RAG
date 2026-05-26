"""
Production RAG Pipeline API
FastAPI application entry point for Phase 8 deployment.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

_LOAD_T0 = time.time()


def _log_load(step: str) -> None:
    print(f"[main.py load] {time.time() - _LOAD_T0:.2f}s - {step}", flush=True)


_log_load("start")


from dotenv import load_dotenv  # noqa: E402

_log_load("dotenv imported")

load_dotenv()  # noqa: E402 - Must load .env before storage modules check os.getenv

_log_load("load_dotenv done")


logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler()],
)
_log_load("logging.basicConfig done")


_log_load("sentry_sdk imported")

from fastapi import Depends, FastAPI  # noqa: E402

_log_load("fastapi imported")

from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

_log_load("cors imported")


_log_load("sentry integrations imported")

from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

_log_load("slowapi imported")

from src.api.middleware.auth import verify_api_key  # noqa: E402
from src.api.middleware.logging import LoggingMiddleware  # noqa: E402
from src.api.middleware.metrics import MetricsMiddleware  # noqa: E402
from src.api.middleware.rate_limit import get_rate_limit_key  # noqa: E402
from src.api.models.models import settings  # noqa: E402

_log_load("local middleware + models imported")

if TYPE_CHECKING:
    from src.ingestion.pipeline import IngestionPipeline
    from src.reasoning.pipeline import ReasoningPipeline
    from src.retrieval.hybrid_search import HybridRetriever

_log_load("Settings() already done in models")

logging.getLogger("src.api.middleware").setLevel(logging.INFO)
logging.getLogger("slowapi").setLevel(logging.WARNING)

limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[f"{max(settings.rate_limit_per_minute, 120)}/minute"],
)

_log_load("Limiter() done")

logger = logging.getLogger(__name__)
_log_load("logger created")

_storage_initialized = False
_reasoning_pipeline = None
_hybrid_retriever = None
_ingestion_pipeline = None


def get_reasoning_pipeline() -> ReasoningPipeline:
    """Lazy-load the reasoning pipeline."""
    global _reasoning_pipeline
    if _reasoning_pipeline is None:
        from src.reasoning.pipeline import ReasoningPipeline

        _reasoning_pipeline = ReasoningPipeline()
        logger.info("ReasoningPipeline initialized")
    return _reasoning_pipeline


def get_hybrid_retriever() -> HybridRetriever:
    """Lazy-load the hybrid retriever."""
    global _hybrid_retriever
    if _hybrid_retriever is None:
        from src.retrieval.hybrid_search import HybridRetriever

        _hybrid_retriever = HybridRetriever()
        logger.info("HybridRetriever initialized")
    return _hybrid_retriever


def get_ingestion_pipeline() -> IngestionPipeline:
    """Lazy-load the ingestion pipeline."""
    global _ingestion_pipeline
    if _ingestion_pipeline is None:
        from src.ingestion.pipeline import IngestionPipeline

        _ingestion_pipeline = IngestionPipeline()
        logger.info("IngestionPipeline initialized")
    return _ingestion_pipeline


def _register_routes(app: FastAPI) -> None:
    """Register API routes (lazy-imported to minimize startup time)."""
    from src.api.routes import health, ingest, metadata, query  # noqa: F811

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(
        query.router,
        prefix="/api/v1",
        tags=["query"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        ingest.router,
        prefix="/api/v1",
        tags=["ingest"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        metadata.router,
        prefix="/api/v1",
        tags=["metadata"],
        dependencies=[Depends(verify_api_key)],
    )
    _log_load("Routes registered")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    global _storage_initialized
    _log_load("Lifespan started")

    # Initialize Sentry for error tracking (graceful no-op if DSN unset)
    # DISABLED: Appears to be blocking startup on Render's hardware/environment
    """
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        _log_load("Sentry DSN found, initializing...")
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration as SentryLoggingIntegration

            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[
                    FastApiIntegration(),
                    SentryLoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
                ],
                traces_sample_rate=0.1,
                send_default_pii=False,
            )
            _log_load("Sentry initialized")
            print("[main.py lifespan] Sentry initialized", flush=True)
        except Exception as e:
            _log_load(f"Sentry initialization failed: {e}")
    """
    _log_load("Sentry initialization skipped (disabled)")

    try:
        app.state.hybrid_retriever = None
        _log_load("Application ready — storage layer will init on first query")
        _storage_initialized = True
    except Exception as e:
        _log_load(f"Storage initialization deferred: {e}")

    _log_load("Lifespan setup complete — yielding")
    yield

    _log_load("Shutting down Production RAG API...")


app = FastAPI(
    title="Production RAG API",
    version="1.0.0",
    description="Production-grade RAG pipeline with LangGraph reasoning engine",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

_log_load("FastAPI() created")

_register_routes(app)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(LoggingMiddleware)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type", "X-Request-ID"],
)

app.add_middleware(MetricsMiddleware)

_log_load("middleware added")


@app.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """Minimal liveness endpoint — no dependencies, always responds."""
    return {"status": "alive"}


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": "Production RAG Pipeline API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }


_log_load("routes defined — module load complete")

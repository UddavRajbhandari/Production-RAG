"""
Production RAG Pipeline API
FastAPI application entry point for Phase 8 deployment.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import sentry_sdk
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.api.middleware.auth import verify_api_key
from src.api.middleware.logging import LoggingMiddleware
from src.api.middleware.rate_limit import get_rate_limit_key
from src.api.models import Settings
from src.api.routes import health, ingest, metadata, query

if TYPE_CHECKING:
    from src.ingestion.pipeline import IngestionPipeline
    from src.reasoning.pipeline import ReasoningPipeline
    from src.retrieval.hybrid_search import HybridRetriever

# Global settings instance
settings = Settings()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler()],
)
# Ensure our middleware logger is specifically set to INFO
logging.getLogger("src.api.middleware").setLevel(logging.INFO)

# Initialize Sentry
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[FastApiIntegration()],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

# Initialize Rate Limiter - per-API-key as per Phase 8 spec
limiter = Limiter(key_func=get_rate_limit_key, default_limits=[f"{settings.rate_limit_per_minute}/minute"])

logger = logging.getLogger(__name__)

# Global module instances (lazy-loaded)
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    global _storage_initialized
    logger.info("Starting Production RAG API...")

    # Pre-initialize storage connections for health checks
    try:
        get_hybrid_retriever()
        logger.info("Storage layer initialized: Qdrant + BM25")
        _storage_initialized = True
    except Exception as e:
        logger.warning("Storage initialization deferred: %s", str(e))

    yield

    logger.info("Shutting down Production RAG API...")


# Create FastAPI application
app = FastAPI(
    title="Production RAG API",
    version="1.0.0",
    description="Production-grade RAG pipeline with LangGraph reasoning engine",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
app.add_middleware(SlowAPIMiddleware)

# Add Structured Logging
app.add_middleware(LoggingMiddleware)

# Configure CORS - explicitly configure for production (not wildcard)
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type", "X-Request-ID"],
)

# Include routers
# Health check remains public
app.include_router(health.router, prefix="/api/v1", tags=["health"])

# Protected routes
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


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": "Production RAG Pipeline API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }

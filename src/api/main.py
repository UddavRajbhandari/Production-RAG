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
from typing import TYPE_CHECKING

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

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

_log_load("fastapi imported")

from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

_log_load("cors imported")

from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

_log_load("slowapi imported")

from src.api.limiter import limiter  # noqa: E402

_log_load("limiter imported")

from src.api.middleware.auth import verify_api_key  # noqa: E402
from src.api.middleware.body_cache import BodyCacheMiddleware  # noqa: E402
from src.api.middleware.logging import LoggingMiddleware  # noqa: E402
from src.api.middleware.metrics import MetricsMiddleware  # noqa: E402

_log_load("local middleware + models imported")

if TYPE_CHECKING:
    from src.ingestion.pipeline import IngestionPipeline
    from src.reasoning.pipeline import ReasoningPipeline
    from src.retrieval.hybrid_search import HybridRetriever

_log_load("Settings() already done in models")

logging.getLogger("src.api.middleware").setLevel(logging.INFO)
logging.getLogger("slowapi").setLevel(logging.WARNING)


# Silence uvicorn access logs for health checks
class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health/live" not in record.getMessage() and "/health/ready" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())

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
    from src.api.routes import health, ingest, metadata, query, session  # noqa: F811

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(session.router, prefix="/api/v1", tags=["session"])
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

    # Sentry disabled — import was blocking on Render's infrastructure.
    # To re-enable: uncomment below and set SENTRY_DSN env var.
    # sentry_dsn = os.getenv("SENTRY_DSN")
    # if sentry_dsn:
    #     try:
    #         import sentry_sdk
    #         from sentry_sdk.integrations.fastapi import FastApiIntegration
    #         from sentry_sdk.integrations.logging import LoggingIntegration as SentryLoggingIntegration
    #         sentry_sdk.init(dsn=sentry_dsn, integrations=[FastApiIntegration(), SentryLoggingIntegration()])
    #     except Exception:
    #         pass
    _log_load("Sentry disabled")

    try:
        app.state.hybrid_retriever = None
        _log_load("Application ready — pre-loading embedding model...")

        import asyncio

        from src.api.routes.ingest import preload_embedding_model

        await asyncio.to_thread(preload_embedding_model)
        _log_load("Embedding model pre-loaded")
        _storage_initialized = True
    except Exception as e:
        _log_load(f"Startup initialization failed: {e}")
        raise

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

# Global OpenAPI security scheme for Swagger "Authorize" button
# This is purely for Swagger UI — actual auth is handled by verify_api_key dependency
from fastapi.openapi.utils import get_openapi  # noqa: E402


def _custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    openapi_schema.setdefault("security", []).append({"ApiKeyAuth": []})
    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = _custom_openapi  # type: ignore[method-assign]

_log_load("FastAPI() created")

_register_routes(app)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Log Pydantic validation errors for debugging."""
    logger.error("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint — shows clean status on HF Spaces App tab."""
    return {"status": "running", "app": "Production RAG API"}


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(LoggingMiddleware)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(MetricsMiddleware)

# BodyCacheMiddleware must be outermost so it reads the raw ASGI stream
# before Starlette's BaseHTTPMiddleware chain can consume it,
# preventing 'input: None' in Pydantic validation.
app.add_middleware(BodyCacheMiddleware)

_log_load("middleware added")


@app.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """Minimal liveness endpoint — no dependencies, always responds."""
    return {"status": "alive"}


_log_load("routes defined — module load complete")

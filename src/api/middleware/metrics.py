"""
Prometheus metrics middleware for production monitoring.

Exposes request counts, latency histograms, and RAGAS score gauges
at the GET /metrics endpoint.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

requests_total = Counter(
    "rag_requests_total",
    "Total HTTP requests by endpoint and status",
    ["endpoint", "status"],
)

latency_histogram = Histogram(
    "rag_latency_seconds",
    "Request latency in seconds by endpoint",
    ["endpoint"],
    buckets=(0.1, 0.5, 1.0, 5.0, 30.0, 60.0, 120.0, 180.0),
)

ragas_gauge = Gauge(
    "rag_ragas_score",
    "Per-query RAGAS evaluation score by metric name",
    ["metric_name"],
)


def update_ragas_metrics(scores: dict[str, float] | None) -> None:
    """Update Prometheus gauges with latest RAGAS scores."""
    if scores is None:
        return
    for metric_name, value in scores.items():
        ragas_gauge.labels(metric_name=metric_name).set(value)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that records request count and latency."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        endpoint = request.url.path
        start = time.time()

        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        except Exception:
            status = "500"
            raise
        finally:
            elapsed = time.time() - start
            requests_total.labels(endpoint=endpoint, status=status).inc()
            latency_histogram.labels(endpoint=endpoint).observe(elapsed)


async def metrics_endpoint(request: Request) -> Response:
    """Return Prometheus-formatted metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
        headers={"Cache-Control": "no-cache"},
    )

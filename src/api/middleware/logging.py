"""
Structured logging middleware with correlation IDs.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured JSON logging and request correlation.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """
        Process the request and log metadata.
        """
        # Skip logging for health checks to reduce noise
        if request.url.path.endswith("/health/live") or request.url.path.endswith("/health/ready"):
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Attach request_id to request state for use in routes
        request.state.request_id = request_id

        start_time = time.time()

        # Pre-processing log
        logger.info(
            json.dumps(
                {
                    "event": "request_received",
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url),
                    "client_ip": request.client.host if request.client else "unknown",
                }
            )
        )

        try:
            response = await call_next(request)

            process_time = time.time() - start_time

            # Ensure response is a Response object for type safety
            if not isinstance(response, Response):
                # This handles cases where call_next might return something else in some frameworks
                # though in FastAPI it should be a Response
                pass

            # Add request ID and process time to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)

            # Post-processing log
            logger.info(
                json.dumps(
                    {
                        "event": "request_completed",
                        "request_id": request_id,
                        "status_code": response.status_code,
                        "duration_s": process_time,
                    }
                )
            )

            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                json.dumps(
                    {
                        "event": "request_failed",
                        "request_id": request_id,
                        "error": str(e),
                        "duration_s": process_time,
                    }
                )
            )
            raise e

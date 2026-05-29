"""
ASGI middleware that caches the request body early.

Starlette's BaseHTTPMiddleware can consume the ASGI receive stream
before FastAPI gets to parse the body, causing `input: None` in
Pydantic validation. This middleware reads the body at the ASGI level
and provides a new receive channel so downstream consumers always
see the full body.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send


class BodyCacheMiddleware:
    """Cache the request body at the ASGI boundary."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        body = b""
        more_body = True
        while more_body:
            message = await receive()
            chunk: bytes = message.get("body", b"")
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            body += chunk
            more_body = message.get("more_body", False)

        body_consumed = False

        async def cached_receive() -> MutableMapping[str, Any]:
            nonlocal body_consumed
            if not body_consumed:
                body_consumed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, cached_receive, send)

"""Unit tests for BodyCacheMiddleware."""

from collections.abc import Callable, Coroutine

import anyio
import pytest

from src.api.middleware.body_cache import BodyCacheMiddleware


class _SinkApp:
    """Minimal ASGI app that records the body it received."""

    def __init__(self) -> None:
        self.body: bytes | None = None
        self.scope_type: str | None = None

    async def __call__(
        self,
        scope: dict,
        receive: Callable[[], Coroutine],
        send: Callable[[dict], Coroutine],
    ) -> None:
        self.scope_type = scope["type"]
        body = b""
        more_body = True
        while more_body:
            msg: dict = await receive()
            body += msg.get("body", b"")
            more_body = msg.get("more_body", False)
        self.body = body
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"OK"})


@pytest.mark.unit
class TestBodyCacheMiddleware:
    """Test suite for body caching middleware."""

    def test_caches_body(self) -> None:
        async def run() -> None:
            sink = _SinkApp()
            mw = BodyCacheMiddleware(sink)

            messages: list[dict] = [
                {"type": "http.request", "body": b'{"query": "hello"}', "more_body": False},
                {"type": "http.disconnect"},
            ]
            index = 0

            async def receive() -> dict:
                nonlocal index
                msg = messages[index]
                index += 1
                return msg

            async def send(msg: dict) -> None:
                pass

            await mw({"type": "http", "method": "POST", "path": "/test"}, receive, send)
            assert sink.body == b'{"query": "hello"}'

        anyio.run(run)

    def test_concatenates_chunks(self) -> None:
        async def run() -> None:
            sink = _SinkApp()
            mw = BodyCacheMiddleware(sink)

            messages: list[dict] = [
                {"type": "http.request", "body": b'{"query": "hel', "more_body": True},
                {"type": "http.request", "body": b'lo"}', "more_body": False},
                {"type": "http.disconnect"},
            ]
            index = 0

            async def receive() -> dict:
                nonlocal index
                msg = messages[index]
                index += 1
                return msg

            async def send(msg: dict) -> None:
                pass

            await mw({"type": "http", "method": "POST", "path": "/test"}, receive, send)
            assert sink.body == b'{"query": "hello"}'

        anyio.run(run)

    def test_non_http_passthrough(self) -> None:
        async def run() -> None:
            sink = _SinkApp()
            mw = BodyCacheMiddleware(sink)

            async def receive() -> dict:
                return {"type": "websocket.connect"}

            async def send(msg: dict) -> None:
                pass

            await mw({"type": "websocket", "path": "/ws"}, receive, send)
            assert sink.scope_type == "websocket"

        anyio.run(run)

    def test_subsequent_receive_returns_disconnect(self) -> None:
        async def run() -> None:
            downstream_receives: list[dict] = []

            async def downstream_app(
                scope: dict,
                recv: Callable[[], Coroutine],
                send: Callable[[dict], Coroutine],
            ) -> None:
                msg1: dict = await recv()
                downstream_receives.append(msg1)
                msg2: dict = await recv()
                downstream_receives.append(msg2)
                await send({"type": "http.response.start", "status": 200, "headers": []})
                await send({"type": "http.response.body", "body": b""})

            mw = BodyCacheMiddleware(downstream_app)

            messages: list[dict] = [
                {"type": "http.request", "body": b'{"x": "y"}', "more_body": False},
                {"type": "http.disconnect"},
            ]
            index = 0

            async def receive() -> dict:
                nonlocal index
                msg = messages[index]
                index += 1
                return msg

            async def send(msg: dict) -> None:
                pass

            await mw({"type": "http", "method": "POST", "path": "/test"}, receive, send)

            assert len(downstream_receives) == 2
            assert downstream_receives[0] == {"type": "http.request", "body": b'{"x": "y"}', "more_body": False}
            assert downstream_receives[1] == {"type": "http.disconnect"}

        anyio.run(run)

    def test_original_receive_not_overconsumed(self) -> None:
        async def run() -> None:
            async def downstream_app(
                scope: dict,
                recv: Callable[[], Coroutine],
                send: Callable[[dict], Coroutine],
            ) -> None:
                await recv()
                await send({"type": "http.response.start", "status": 200, "headers": []})
                await send({"type": "http.response.body", "body": b""})

            mw = BodyCacheMiddleware(downstream_app)

            messages: list[dict] = [
                {"type": "http.request", "body": b'{"a": 1}', "more_body": False},
                {"type": "http.disconnect"},
            ]
            index = 0
            original_calls: list[dict] = []

            async def receive() -> dict:
                nonlocal index
                msg = messages[index]
                index += 1
                original_calls.append(msg)
                return msg

            async def send(msg: dict) -> None:
                pass

            await mw({"type": "http", "method": "POST", "path": "/test"}, receive, send)

            http_msgs = [m for m in original_calls if m["type"] == "http.request"]
            disc_msgs = [m for m in original_calls if m["type"] == "http.disconnect"]
            assert len(http_msgs) == 1
            assert len(disc_msgs) == 0

        anyio.run(run)

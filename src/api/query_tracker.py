"""
In-flight query tracker for stuck query detection and recovery.

Tracks every active query with a start timestamp. Provides:
- Monitoring: list all active queries and their ages
- Stale detection: identify queries exceeding threshold
- Cleanup: remove stale entries
"""

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_STALE_TIMEOUT_S = 300  # 5 minutes — queries older than this are considered stale


class QueryTracker:
    """Thread-safe tracker of in-flight queries."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: dict[str, dict[str, Any]] = {}

    def start(self, request_id: str, query: str, tenant_id: str = "") -> None:
        """Register a query as in-flight."""
        with self._lock:
            self._active[request_id] = {
                "query": query[:200],
                "tenant_id": tenant_id,
                "start_time": time.time(),
                "node": "",
            }

    def update_node(self, request_id: str, node: str) -> None:
        """Update which node the query is currently in."""
        with self._lock:
            if request_id in self._active:
                self._active[request_id]["node"] = node

    def finish(self, request_id: str) -> None:
        """Remove a completed query from tracking."""
        with self._lock:
            self._active.pop(request_id, None)

    def get_active(self, tenant_id: str = "") -> dict[str, dict[str, Any]]:
        """Return snapshot of all in-flight queries, optionally scoped to a tenant."""
        now = time.time()
        with self._lock:
            if tenant_id:
                items = [(rid, info) for rid, info in self._active.items() if info.get("tenant_id") == tenant_id]
            else:
                items = list(self._active.items())
            return {
                rid: {
                    "query": info["query"],
                    "age_s": round(now - info["start_time"], 1),
                    "node": info["node"],
                    "stale": (now - info["start_time"]) > _STALE_TIMEOUT_S,
                }
                for rid, info in items
            }

    def get_stale(self) -> list[str]:
        """Return request IDs of queries that have exceeded the stale timeout."""
        now = time.time()
        with self._lock:
            return [rid for rid, info in self._active.items() if (now - info["start_time"]) > _STALE_TIMEOUT_S]

    def force_clear(self, request_id: str, tenant_id: str = "") -> bool:
        """Forcefully remove a query from tracking. Returns True if it existed.

        Only removes if the request belongs to the given tenant (if tenant_id provided).
        """
        with self._lock:
            if tenant_id and self._active.get(request_id, {}).get("tenant_id") != tenant_id:
                return False
            existed = request_id in self._active
            self._active.pop(request_id, None)
            return existed

    def active_count(self) -> int:
        """Number of currently in-flight queries."""
        with self._lock:
            return len(self._active)


# Global singleton
query_tracker = QueryTracker()

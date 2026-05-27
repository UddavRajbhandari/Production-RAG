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

    def start(self, request_id: str, query: str) -> None:
        """Register a query as in-flight."""
        with self._lock:
            self._active[request_id] = {
                "query": query[:200],
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

    def get_active(self) -> dict[str, dict[str, Any]]:
        """Return snapshot of all in-flight queries."""
        now = time.time()
        with self._lock:
            return {
                rid: {
                    "query": info["query"],
                    "age_s": round(now - info["start_time"], 1),
                    "node": info["node"],
                    "stale": (now - info["start_time"]) > _STALE_TIMEOUT_S,
                }
                for rid, info in self._active.items()
            }

    def get_stale(self) -> list[str]:
        """Return request IDs of queries that have exceeded the stale timeout."""
        now = time.time()
        with self._lock:
            return [rid for rid, info in self._active.items() if (now - info["start_time"]) > _STALE_TIMEOUT_S]

    def force_clear(self, request_id: str) -> bool:
        """Forcefully remove a query from tracking. Returns True if it existed."""
        with self._lock:
            existed = request_id in self._active
            self._active.pop(request_id, None)
            return existed

    def active_count(self) -> int:
        """Number of currently in-flight queries."""
        with self._lock:
            return len(self._active)


# Global singleton
query_tracker = QueryTracker()

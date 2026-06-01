"""
Custom rate limiter key function that uses tenant_id from session
cookie when available, falls back to IP.
"""

from __future__ import annotations

from fastapi import Request
from slowapi.util import get_remote_address


def get_rate_limit_key(request: Request) -> str:
    """
    Use tenant_id from session cookie as rate limit key when available,
    fallback to IP address.

    Args:
        request: The incoming request.

    Returns:
        The rate limit key (tenant_id or IP address).
    """
    session_token = request.cookies.get("session")
    if session_token:
        return f"tenant:{session_token[:16]}"
    return f"ip:{get_remote_address(request)}"

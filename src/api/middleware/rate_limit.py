"""
Custom rate limiter key function that uses API key when available, falls back to IP.
"""

from __future__ import annotations

from fastapi import Request
from slowapi.util import get_remote_address


def get_rate_limit_key(request: Request) -> str:
    """
    Use API key as rate limit key when available, fallback to IP address.

    This implements per-API-key rate limiting as specified in Phase 8:
    "60 requests/minute per API key"

    Args:
        request: The incoming request.

    Returns:
        The rate limit key (API key or IP address).
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api_key:{api_key}"
    return f"ip:{get_remote_address(request)}"

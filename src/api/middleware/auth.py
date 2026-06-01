"""
API Key authentication middleware.

Validates the HttpOnly session cookie set by /session/init and attaches
tenant_id to request.state for downstream tenant-scoped filtering.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request

from src.api.middleware.session import verify_session_token

logger = logging.getLogger(__name__)

_EXEMPT_PREFIXES = ("/api/v1/health", "/api/v1/session", "/health/")


async def verify_api_key(request: Request) -> str:
    """
    Verify the session cookie and attach tenant_id to request.state.

    Exempts health, session/init, and root endpoints.
    """
    path = request.url.path
    if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
        return ""

    session_token = request.cookies.get("session")
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Call /api/v1/session/init first.",
        )

    tenant_id = verify_session_token(session_token)
    if not tenant_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session. Re-initialize at /api/v1/session/init.",
        )

    request.state.tenant_id = tenant_id
    return session_token

"""
API Key authentication middleware.

Validates the HttpOnly session cookie (default) or X-Tenant-ID header (fallback
for cross-origin file uploads that bypass the Vercel proxy).

The session cookie is HMAC-signed and preferred. The X-Tenant-ID header is a
weaker fallback — it accepts any valid tenant_id since these are already visible
in the frontend — used only for direct file uploads to avoid Vercel's 4.5MB
Serverless Function body limit.
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

    Falls back to X-Tenant-ID header for cross-origin requests (e.g. direct
    file uploads bypassing the Vercel proxy).

    Exempts health, session/init, and root endpoints.
    """
    path = request.url.path
    if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
        return ""

    session_token = request.cookies.get("session")
    if session_token:
        tenant_id = verify_session_token(session_token)
        if tenant_id:
            request.state.tenant_id = tenant_id
            return session_token
        # Session cookie present but invalid (expired or tampered)
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_session",
                "message": "Your session has expired or is invalid. Please start a new session.",
                "solution": "Call /api/v1/session/init to create a new session.",
            },
        )

    # Fallback: X-Tenant-ID header (weaker auth, for cross-origin uploads)
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        from src.storage.tenant_store import get_tenant_store

        if get_tenant_store().tenant_exists(tenant_id):
            request.state.tenant_id = tenant_id
            return tenant_id
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_tenant",
                "message": f"Tenant ID '{tenant_id}' does not exist.",
                "solution": "Provide a valid Tenant ID or call /api/v1/session/init to create a new session.",
            },
        )

    raise HTTPException(
        status_code=401,
        detail={
            "error": "not_authenticated",
            "message": "Not authenticated. No session cookie or Tenant ID provided.",
            "solution": "Call /api/v1/session/init first to create a session.",
        },
    )

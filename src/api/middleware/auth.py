"""
API Key authentication middleware.

Validates X-API-Key against TenantStore and attaches tenant_id
to request.state for downstream tenant-scoped filtering.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

API_KEY_NAME = "X-API-Key"  # pragma: allowlist secret

_EXEMPT_PREFIXES = ("/api/v1/health", "/api/v1/session", "/health/")


async def verify_api_key(request: Request) -> str:
    """
    Verify the API key and attach tenant_id to request.state.

    Exempts health, session/init, and root endpoints.
    """
    path = request.url.path
    if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
        return ""

    api_key = request.headers.get(API_KEY_NAME)
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API Key. Provide X-API-Key header.",
        )

    from src.storage.tenant_store import get_tenant_store

    store = get_tenant_store()
    tenant_id = store.lookup_tenant(api_key)

    if not tenant_id:
        logger.warning("Invalid API key provided for request to %s", path)
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key.",
        )

    request.state.tenant_id = tenant_id
    return api_key

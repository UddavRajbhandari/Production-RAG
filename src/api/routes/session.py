"""
Session initialization endpoint.
Auto-provisions a tenant_id for first-time visitors.
Sets an HttpOnly signed cookie for subsequent auth.

Accepts an optional previous tenant_id so users can reclaim their data
after cookie expiry or server restarts.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from src.api.middleware.session import create_session_token
from src.storage.tenant_store import get_tenant_store

logger = logging.getLogger(__name__)

router = APIRouter()


class InitSessionRequest(BaseModel):
    tenant_id: str | None = None


@router.post("/session/init")
async def init_session(request: Request, response: Response, body: InitSessionRequest | None = None) -> dict:
    """Generate or restore a tenant and set a signed HttpOnly cookie.

    If tenant_id is provided and exists in the database, re-issues the
    cookie for that tenant (data is preserved). Otherwise creates a new
    tenant.
    """
    store = get_tenant_store()
    requested_id = body.tenant_id if body and body.tenant_id else None

    if requested_id and store.tenant_exists(requested_id):
        tenant_id = requested_id
        logger.info("Restoring session for existing tenant=%s", tenant_id)
    else:
        _, tenant_id = store.create_tenant()
        logger.info("New session provisioned: tenant=%s", tenant_id)

    token = create_session_token(tenant_id)
    is_secure = request.url.scheme == "https"
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=86400,
        path="/",
    )
    return {"tenant_id": tenant_id}

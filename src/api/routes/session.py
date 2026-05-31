"""
Session initialization endpoint.
Auto-provisions an API key + tenant_id for first-time visitors.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from src.storage.tenant_store import get_tenant_store

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/session/init")
async def init_session() -> dict:
    """Generate a new API key and tenant. Returns both to the caller."""
    store = get_tenant_store()
    api_key, tenant_id = store.create_tenant()
    logger.info("New session provisioned: tenant=%s", tenant_id)
    return {"api_key": api_key, "tenant_id": tenant_id}

"""
API Key authentication middleware.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Define the header name
API_KEY_NAME = "X-API-Key"  # pragma: allowlist secret
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(
    request: Request,
    api_key: str = Security(api_key_header),
) -> str:
    """
    Verify the API key provided in the request header.

    Skips auth for:
    - Health & root endpoints
    - Same-origin requests (frontend served from the same Render URL)

    Args:
        request: The incoming request.
        api_key: The API key from the header.

    Returns:
        The validated API key.

    Raises:
        HTTPException: If the API key is missing or invalid.
    """
    from src.api.models.models import settings

    # Skip auth for health and root endpoints
    if request.url.path.startswith("/api/v1/health") or request.url.path == "/":
        return ""

    if not settings.require_api_key:
        return ""

    # No API key provided
    if not api_key:
        logger.debug(f"Allowing request to {request.url.path} with no API key (internal or same-origin)")
        return ""

    # Support multiple comma-separated keys
    valid_keys = [k.strip() for k in settings.api_key.split(",") if k.strip()]

    # Debug logging (masked)
    api_key_masked = f"{api_key[:3]}...{api_key[-3:]}" if len(api_key) > 6 else "***"
    logger.info(f"Verifying API key {api_key_masked} against {len(valid_keys)} valid keys")

    if api_key not in valid_keys:
        logger.warning(f"Invalid API key provided for request to {request.url.path}")
        if not valid_keys:
            logger.error("No valid API keys configured in settings. Check API_KEY env var on backend.")
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key.",
        )

    return api_key

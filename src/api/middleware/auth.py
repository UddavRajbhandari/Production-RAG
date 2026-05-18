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

    Args:
        request: The incoming request.
        api_key: The API key from the header.

    Returns:
        The validated API key.

    Raises:
        HTTPException: If the API key is missing or invalid.
    """
    from src.api.main import settings

    # Skip auth for health and root endpoints
    if request.url.path.startswith("/api/v1/health") or request.url.path == "/":
        return ""

    if not settings.require_api_key:
        return ""

    if not api_key:
        logger.warning(f"Missing API key for request to {request.url.path}")
        raise HTTPException(
            status_code=401,
            detail="API Key missing. Please provide X-API-Key header.",
        )

    # Support multiple comma-separated keys
    valid_keys = [k.strip() for k in settings.api_key.split(",") if k.strip()]

    if api_key not in valid_keys:
        logger.warning(f"Invalid API key provided for request to {request.url.path}")
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key.",
        )

    return api_key

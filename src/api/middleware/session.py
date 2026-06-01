"""
Session cookie utilities for HttpOnly cookie-based auth.

Uses HMAC-signed cookies so tenant_id is never exposed to JavaScript.
No additional dependencies required.
"""

from __future__ import annotations

import base64
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, cast

logger = logging.getLogger(__name__)

_SESSION_SECRET: str | None = None
_SESSION_TTL_S = 86400  # 24 hours


def _get_secret() -> str:
    global _SESSION_SECRET
    if _SESSION_SECRET is None:
        _SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
        logger.info("Session secret initialized")
    return _SESSION_SECRET


def create_session_token(tenant_id: str) -> str:
    payload: dict[str, Any] = {
        "t": tenant_id,
        "e": int(time.time()) + _SESSION_TTL_S,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(_get_secret().encode(), payload_b64.encode(), "sha256").hexdigest()[:16]
    return f"{payload_b64}.{sig}"


def verify_session_token(token: str) -> str | None:
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected = hmac.new(_get_secret().encode(), payload_b64.encode(), "sha256").hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            return None
        padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        data: dict[str, Any] = json.loads(base64.urlsafe_b64decode(padded))
        if data["e"] < time.time():
            return None
        return cast(str, data["t"])
    except Exception:
        return None

"""
Shared rate limiter instance.
Extracted to its own module to avoid circular imports between main.py and query.py.
"""

from slowapi import Limiter

from src.api.middleware.rate_limit import get_rate_limit_key
from src.api.models.models import settings

limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
)

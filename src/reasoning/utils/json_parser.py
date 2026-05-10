"""
Safe JSON Parser
Provides robust JSON parsing with fallback handling for malformed LLM responses.
"""

import json
import logging
import re
from typing import Any, cast

logger = logging.getLogger(__name__)


def safe_json_parse(
    raw_response: str,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Parse JSON from LLM response with multiple fallback strategies.

    Args:
        raw_response: Raw string response from LLM
        default: Default dict to return if all parsing attempts fail

    Returns:
        Parsed JSON as dict, or default value
    """
    if default is None:
        default = {}

    if not raw_response or not raw_response.strip():
        logger.warning("Empty response received for JSON parsing")
        return default

    # Strategy 1: Direct parse
    try:
        parsed = json.loads(raw_response)
        return cast(dict[str, Any], parsed)
    except json.JSONDecodeError:
        logger.debug("Direct JSON parse failed, trying cleanup strategies")

    # Strategy 2: Extract JSON object from response
    # Look for {...} pattern in the response
    json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
    match = re.search(json_pattern, raw_response, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return cast(dict[str, Any], parsed)
        except json.JSONDecodeError:
            logger.debug("Regex extraction failed")

    # Strategy 3: Try to fix common JSON issues
    # Remove trailing commas, fix single quotes
    cleaned = raw_response
    cleaned = re.sub(r",\s*}", "}", cleaned)
    cleaned = re.sub(r",\s*]", "]", cleaned)
    cleaned = re.sub(r"'([^']*)'", r'"\1"', cleaned)

    try:
        parsed = json.loads(cleaned)
        return cast(dict[str, Any], parsed)
    except json.JSONDecodeError:
        logger.warning("All JSON parsing strategies failed, returning default")
        return default

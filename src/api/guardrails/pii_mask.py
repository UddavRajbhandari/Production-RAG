"""
PII Masking — detects and redacts Personally Identifiable Information.

Covers: emails, phone numbers, SSNs, credit card numbers, IP addresses.
Applied at both input (query) and output (response) layers.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Regex patterns grouped by PII type
PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
}

REDACTION_TOKENS: dict[str, str] = {
    "email": "[REDACTED_EMAIL]",
    "phone": "[REDACTED_PHONE]",
    "ssn": "[REDACTED_SSN]",
    "credit_card": "[REDACTED_CC]",
    "ip_address": "[REDACTED_IP]",
}

SCORE_WEIGHTS: dict[str, int] = {
    "email": 3,
    "phone": 2,
    "ssn": 5,
    "credit_card": 5,
    "ip_address": 2,
}


class PIIMask:
    """Detects and redacts PII in text."""

    def __init__(self, threshold: int = 3) -> None:
        self.threshold = threshold

    def scan(self, text: str) -> list[dict[str, Any]]:
        """Scan text and return list of detected PII items."""
        findings: list[dict[str, Any]] = []
        for pii_type, pattern in PII_PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append(
                    {
                        "type": pii_type,
                        "value": match.group(),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
        return findings

    def contains_pii(self, text: str) -> bool:
        """Check if text contains any PII."""
        return len(self.scan(text)) > 0

    def redact(self, text: str) -> str:
        """Redact all PII in text with type-specific tokens."""
        result = text
        for pii_type, pattern in PII_PATTERNS.items():
            token = REDACTION_TOKENS[pii_type]
            result = pattern.sub(token, result)
        return result

    def score_text(self, text: str) -> int:
        """Score the severity of PII content in text."""
        findings = self.scan(text)
        return sum(SCORE_WEIGHTS.get(f["type"], 1) for f in findings)

    def is_sensitive(self, text: str) -> bool:
        """Return True if text exceeds the sensitivity threshold."""
        return self.score_text(text) >= self.threshold

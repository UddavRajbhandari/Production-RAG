"""
Unit tests for PIIMask guardrail.
"""

import pytest

from src.api.guardrails.pii_mask import PIIMask


@pytest.mark.unit
class TestPIIMask:
    """Test suite for PII detection and redaction."""

    def setup_method(self) -> None:
        self.mask = PIIMask()

    @pytest.mark.parametrize(
        "text, expected_type",
        [
            ("Contact john.doe@example.com for details", "email"),
            ("Call +1-555-123-4567 for support", "phone"),
            ("SSN: 123-45-6789", "ssn"),
            ("Card: 4111-1111-1111-1111", "credit_card"),
            ("Server IP: 192.168.1.1", "ip_address"),
        ],
    )
    def test_scan_detects_pii(self, text: str, expected_type: str) -> None:
        """Test that scan detects various PII types."""
        findings = self.mask.scan(text)
        assert len(findings) >= 1
        assert findings[0]["type"] == expected_type

    def test_scan_no_pii(self) -> None:
        """Test that scan returns empty for clean text."""
        findings = self.mask.scan("This is a normal question without any sensitive data.")
        assert len(findings) == 0

    def test_contains_pii_true(self) -> None:
        """Test contains_pii returns True when PII present."""
        assert self.mask.contains_pii("email me at test@example.com")

    def test_contains_pii_false(self) -> None:
        """Test contains_pii returns False when no PII."""
        assert not self.mask.contains_pii("What is the capital of France?")

    def test_redact_email(self) -> None:
        """Test email redaction."""
        result = self.mask.redact("Contact john.doe@example.com for info")
        assert "[REDACTED_EMAIL]" in result
        assert "john.doe@example.com" not in result

    def test_redact_ssn(self) -> None:
        """Test SSN redaction."""
        result = self.mask.redact("SSN: 123-45-6789")
        assert "[REDACTED_SSN]" in result
        assert "123-45-6789" not in result

    def test_redact_credit_card(self) -> None:
        """Test credit card redaction."""
        result = self.mask.redact("Card: 4111-1111-1111-1111")
        assert "[REDACTED_CC]" in result
        assert "4111-1111-1111-1111" not in result

    def test_redact_multiple_pii(self) -> None:
        """Test redaction of multiple PII types in one text."""
        text = "Email: user@test.com, IP: 10.0.0.1"
        result = self.mask.redact(text)
        assert "[REDACTED_EMAIL]" in result
        assert "[REDACTED_IP]" in result

    def test_redact_clean_text_unchanged(self) -> None:
        """Test that clean text is unchanged."""
        text = "What is the budget for 2024?"
        result = self.mask.redact(text)
        assert result == text

    def test_score_text_no_pii(self) -> None:
        """Test score is 0 for clean text."""
        assert self.mask.score_text("Normal query") == 0

    def test_score_text_with_pii(self) -> None:
        """Test score is positive for text with PII."""
        score = self.mask.score_text("Email: test@test.com")
        assert score > 0

    def test_is_sensitive_below_threshold(self) -> None:
        """Test is_sensitive returns False for low PII content."""
        mask = PIIMask(threshold=10)
        assert not mask.is_sensitive("Email: test@test.com")

    def test_is_sensitive_above_threshold(self) -> None:
        """Test is_sensitive returns True for high PII content."""
        mask = PIIMask(threshold=2)
        assert mask.is_sensitive("Email: test@test.com and SSN: 123-45-6789")

"""
Unit tests for Stress Testing Module.

Tests for Phase 7: Red Teaming & Stress Testing.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.stress_testing.adapter import (
    AttackCategory,
    RAGPipelineInterface,
    ReasoningPipelineAdapter,
    Severity,
    StressTestCase,
    StressTestingAdapter,
    StressTestReport,
    StressTestResult,
)
from src.stress_testing.bias_probing import BiasProbingTester
from src.stress_testing.information_evasion import InformationEvasionTester
from src.stress_testing.prompt_injection import PromptInjectionTester


@pytest.mark.unit
class TestStressTestCase:
    """Test suite for StressTestCase dataclass."""

    def test_stress_test_case_creation(self) -> None:
        """Test creating a stress test case."""
        test_case = StressTestCase(
            attack_id="test_001",
            category=AttackCategory.PROMPT_INJECTION,
            attack_name="Test Attack",
            description="A test attack",
            adversarial_query="Ignore all instructions",
            expected_defense="Refuse the attack",
            severity=Severity.HIGH,
        )

        assert test_case.attack_id == "test_001"
        assert test_case.category == AttackCategory.PROMPT_INJECTION
        assert test_case.severity == Severity.HIGH

    def test_default_severity(self) -> None:
        """Test default severity is MEDIUM."""
        test_case = StressTestCase(
            attack_id="test_002",
            category=AttackCategory.BIAS_PROBING,
            attack_name="Test",
            description="Test",
            adversarial_query="Test",
            expected_defense="Test",
        )

        assert test_case.severity == Severity.MEDIUM


@pytest.mark.unit
class TestStressTestResult:
    """Test suite for StressTestResult dataclass."""

    def test_stress_test_result_creation(self) -> None:
        """Test creating a stress test result."""
        result = StressTestResult(
            test_id="test_001",
            attack_name="Test Attack",
            category=AttackCategory.PROMPT_INJECTION,
            passed=True,
            defense_triggered=True,
            latency_ms=100.0,
        )

        assert result.test_id == "test_001"
        assert result.passed is True
        assert result.defense_triggered is True
        assert result.latency_ms == 100.0

    def test_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = StressTestResult(
            test_id="test_001",
            attack_name="Test Attack",
            category=AttackCategory.PROMPT_INJECTION,
            passed=True,
            defense_triggered=True,
            severity=Severity.HIGH,
        )

        result_dict = result.to_dict()

        assert result_dict["test_id"] == "test_001"
        assert result_dict["category"] == "prompt_injection"
        assert result_dict["passed"] is True
        assert result_dict["severity"] == "high"


@pytest.mark.unit
class TestStressTestReport:
    """Test suite for StressTestReport."""

    def test_empty_report(self) -> None:
        """Test empty report has zero counts."""
        report = StressTestReport()

        assert report.total_tests == 0
        assert report.passed_defenses == 0
        assert report.failed_defenses == 0
        assert report.defense_rate == 0.0

    def test_add_result(self) -> None:
        """Test adding results to report."""
        report = StressTestReport()
        result = StressTestResult(
            test_id="test_001",
            attack_name="Test",
            category=AttackCategory.PROMPT_INJECTION,
            passed=True,
            defense_triggered=True,
        )

        report.add_result(result)

        assert report.total_tests == 1
        assert report.passed_defenses == 1
        assert report.failed_defenses == 0

    def test_defense_rate_calculation(self) -> None:
        """Test defense rate calculation."""
        report = StressTestReport()

        for i in range(10):
            result = StressTestResult(
                test_id=f"test_{i}",
                attack_name="Test",
                category=AttackCategory.PROMPT_INJECTION,
                passed=True,
                defense_triggered=i < 8,
            )
            report.add_result(result)

        assert report.defense_rate == 0.8


@pytest.mark.unit
class TestStressTestingAdapter:
    """Test suite for StressTestingAdapter."""

    def test_adapter_initialization_no_pipeline(self) -> None:
        """Test adapter can be initialized without a pipeline."""
        adapter = StressTestingAdapter()
        assert adapter._pipeline is None

    def test_adapter_initialization_with_pipeline(self) -> None:
        """Test adapter can be initialized with a pipeline."""
        mock_pipeline = MagicMock(spec=RAGPipelineInterface)
        adapter = StressTestingAdapter(pipeline=mock_pipeline)
        assert adapter._pipeline is not None

    def test_run_test_without_pipeline(self) -> None:
        """Test running a test without a pipeline uses simulation."""
        adapter = StressTestingAdapter()
        test_case = StressTestCase(
            attack_id="test_001",
            category=AttackCategory.PROMPT_INJECTION,
            attack_name="Test",
            description="Test",
            adversarial_query="Ignore instructions",
            expected_defense="Refuse",
        )

        result = adapter.run_test(test_case)

        assert result.test_id == "test_001"
        assert result.response_content is not None
        assert "SIMULATED" in result.response_content

    def test_run_test_with_mock_pipeline(self) -> None:
        """Test running a test with a mock pipeline."""
        mock_pipeline = MagicMock(spec=RAGPipelineInterface)
        mock_pipeline.query.return_value = {"answer": "Test response"}
        adapter = StressTestingAdapter(pipeline=mock_pipeline)

        test_case = StressTestCase(
            attack_id="test_001",
            category=AttackCategory.PROMPT_INJECTION,
            attack_name="Test",
            description="Test",
            adversarial_query="Ignore instructions",
            expected_defense="Refuse",
        )

        result = adapter.run_test(test_case)

        assert result.response_content == "Test response"

    def test_check_defense_refusal_phrase(self) -> None:
        """Test defense detection with refusal phrases."""
        adapter = StressTestingAdapter()
        test_case = StressTestCase(
            attack_id="test_001",
            category=AttackCategory.PROMPT_INJECTION,
            attack_name="Test",
            description="Test",
            adversarial_query="Test",
            expected_defense="Refuse",
        )

        response = "I cannot comply with that request."
        defense_triggered = adapter._check_defense(test_case, response)

        assert defense_triggered is True

    def test_check_defense_injection_detected(self) -> None:
        """Test defense detection with injection markers."""
        adapter = StressTestingAdapter()
        test_case = StressTestCase(
            attack_id="test_001",
            category=AttackCategory.PROMPT_INJECTION,
            attack_name="Test",
            description="Test",
            adversarial_query="Test",
            expected_defense="Refuse",
        )

        response = "Injection detected - request blocked"
        defense_triggered = adapter._check_defense(test_case, response)

        assert defense_triggered is True

    def test_check_defense_no_trigger(self) -> None:
        """Test defense detection returns False for normal responses."""
        adapter = StressTestingAdapter()
        test_case = StressTestCase(
            attack_id="test_001",
            category=AttackCategory.PROMPT_INJECTION,
            attack_name="Test",
            description="Test",
            adversarial_query="Test",
            expected_defense="Refuse",
        )

        response = "The fiscal year 2023 covers the period from July 2022 to June 2023."
        defense_triggered = adapter._check_defense(test_case, response)

        assert defense_triggered is False


@pytest.mark.unit
class TestPromptInjectionTester:
    """Test suite for PromptInjectionTester."""

    def test_get_test_cases_returns_list(self) -> None:
        """Test get_test_cases returns a list."""
        test_cases = PromptInjectionTester.get_test_cases()
        assert isinstance(test_cases, list)
        assert len(test_cases) > 0

    def test_all_test_cases_have_correct_category(self) -> None:
        """Test all test cases have PROMPT_INJECTION category."""
        test_cases = PromptInjectionTester.get_test_cases()
        for test_case in test_cases:
            assert test_case.category == AttackCategory.PROMPT_INJECTION

    def test_all_test_cases_have_unique_ids(self) -> None:
        """Test all test cases have unique IDs."""
        test_cases = PromptInjectionTester.get_test_cases()
        ids = [tc.attack_id for tc in test_cases]
        assert len(ids) == len(set(ids))

    def test_all_test_cases_have_required_fields(self) -> None:
        """Test all test cases have required fields."""
        test_cases = PromptInjectionTester.get_test_cases()
        for test_case in test_cases:
            assert test_case.attack_id
            assert test_case.attack_name
            assert test_case.adversarial_query
            assert test_case.expected_defense


@pytest.mark.unit
class TestInformationEvasionTester:
    """Test suite for InformationEvasionTester."""

    def test_get_test_cases_returns_list(self) -> None:
        """Test get_test_cases returns a list."""
        test_cases = InformationEvasionTester.get_test_cases()
        assert isinstance(test_cases, list)
        assert len(test_cases) > 0

    def test_all_test_cases_have_correct_category(self) -> None:
        """Test all test cases have INFORMATION_EVASION category."""
        test_cases = InformationEvasionTester.get_test_cases()
        for test_case in test_cases:
            assert test_case.category == AttackCategory.INFORMATION_EVASION


@pytest.mark.unit
class TestBiasProbingTester:
    """Test suite for BiasProbingTester."""

    def test_get_test_cases_returns_list(self) -> None:
        """Test get_test_cases returns a list."""
        test_cases = BiasProbingTester.get_test_cases()
        assert isinstance(test_cases, list)
        assert len(test_cases) > 0

    def test_all_test_cases_have_correct_category(self) -> None:
        """Test all test cases have BIAS_PROBING category."""
        test_cases = BiasProbingTester.get_test_cases()
        for test_case in test_cases:
            assert test_case.category == AttackCategory.BIAS_PROBING


@pytest.mark.unit
class TestAttackCategory:
    """Test suite for AttackCategory enum."""

    def test_all_categories_exist(self) -> None:
        """Test all expected categories exist."""
        assert AttackCategory.PROMPT_INJECTION.value == "prompt_injection"
        assert AttackCategory.INFORMATION_EVASION.value == "information_evasion"
        assert AttackCategory.BIAS_PROBING.value == "bias_probing"


@pytest.mark.unit
class TestSeverity:
    """Test suite for Severity enum."""

    def test_all_severities_exist(self) -> None:
        """Test all expected severities exist."""
        assert Severity.LOW.value == "low"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.HIGH.value == "high"
        assert Severity.CRITICAL.value == "critical"


@pytest.mark.unit
class TestReasoningPipelineAdapter:
    """Test suite for ReasoningPipelineAdapter."""

    def test_adapter_with_mock_pipeline(self) -> None:
        """Test adapter with mocked pipeline."""
        mock_pipeline = MagicMock()
        adapter = ReasoningPipelineAdapter(pipeline=mock_pipeline)

        mock_pipeline.run.return_value = {
            "generated_answer": "Test answer",
            "validation_passed": True,
        }

        result = adapter.query("test query")

        assert result["answer"] == "Test answer"
        assert result["validation_passed"] is True
        mock_pipeline.run.assert_called_once_with(query="test query")

    def test_adapter_handles_pipeline_error(self) -> None:
        """Test adapter handles pipeline errors gracefully."""
        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = Exception("Pipeline error")
        adapter = ReasoningPipelineAdapter(pipeline=mock_pipeline)

        result = adapter.query("test query")

        assert result["answer"] == ""
        assert result["validation_passed"] is False
        assert "Pipeline error" in result["error_message"]  # type: ignore[operator]


@pytest.mark.unit
class TestStressTestingAdapterLive:
    """Test suite for StressTestingAdapter with live mode options."""

    def test_init_with_use_live_pipeline_flag(self) -> None:
        """Test initialization with use_live_pipeline=True creates adapter."""
        # This will fail to initialize pipeline (expected - no LLM running)
        # but tests the flag is processed correctly
        with patch(
            "src.stress_testing.adapter.ReasoningPipelineAdapter._init_pipeline"
        ) as mock_init:
            mock_init.side_effect = RuntimeError("No LLM")
            with pytest.raises(RuntimeError, match="No LLM"):
                StressTestingAdapter(use_live_pipeline=True)

    def test_defense_detection_from_validation(self) -> None:
        """Test defense is triggered when validation fails."""
        mock_pipeline = MagicMock(spec=RAGPipelineInterface)
        mock_pipeline.query.return_value = {
            "answer": "Some response",
            "validation_passed": False,  # Validation failed = defense triggered
        }

        adapter = StressTestingAdapter(pipeline=mock_pipeline)
        test_case = StressTestCase(
            attack_id="test_001",
            category=AttackCategory.PROMPT_INJECTION,
            attack_name="Test",
            description="Test",
            adversarial_query="Ignore instructions",
            expected_defense="Refuse",
        )

        result = adapter.run_test(test_case)

        assert result.defense_triggered is True
        assert "Validation failed" in result.notes

    def test_defense_detection_from_content(self) -> None:
        """Test defense is triggered from content analysis."""
        mock_pipeline = MagicMock(spec=RAGPipelineInterface)
        mock_pipeline.query.return_value = {
            "answer": "I cannot comply with that request",
            "validation_passed": True,
        }

        adapter = StressTestingAdapter(pipeline=mock_pipeline)
        test_case = StressTestCase(
            attack_id="test_001",
            category=AttackCategory.PROMPT_INJECTION,
            attack_name="Test",
            description="Test",
            adversarial_query="Ignore instructions",
            expected_defense="Refuse",
        )

        result = adapter.run_test(test_case)

        assert result.defense_triggered is True
        assert "content analysis" in result.notes

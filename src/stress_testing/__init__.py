"""
Stress Testing Module for Phase 7: Red Teaming.

This module provides adversarial testing capabilities to stress test the RAG pipeline:
- Prompt Injection: Tests for malicious prompt manipulation
- Information Evasion: Tests for attempts to withhold information
- Bias Probing: Tests for demographic, political, and social biases
"""

from src.stress_testing.adapter import (
    AttackCategory,
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

__all__ = [
    # Core classes
    "StressTestingAdapter",
    "ReasoningPipelineAdapter",
    "StressTestCase",
    "StressTestReport",
    "StressTestResult",
    # Enums
    "AttackCategory",
    "Severity",
    # Testers
    "PromptInjectionTester",
    "InformationEvasionTester",
    "BiasProbingTester",
]

"""
Integration tests for RAGAS Evaluation.
Tests the evaluation pipeline on a small subset of ground truth data.
"""

import json
import os

import pytest

from src.evaluation.evaluate_ragas import (
    compute_answer_completeness,
    compute_context_precision,
    load_ground_truth,
)


@pytest.mark.integration
class TestEvaluationMetrics:
    """Test evaluation metric calculations."""

    def test_load_ground_truth(self) -> None:
        """Test loading ground truth dataset."""
        path = "data/ground_truth/ground_truth.json"
        if os.path.exists(path):
            data = load_ground_truth(path)
            assert len(data) > 0
            assert "question" in data[0]
            assert "ground_truth_answer" in data[0]

    def test_compute_context_precision_with_relevant_context(self) -> None:
        """Test precision calculation with relevant context."""
        question = "What is the fiscal year 2023 period?"
        contexts = [
            "The fiscal year 2023 covers July 1, 2022 to June 30, 2023.",
            "FY23 is the period from July 2022 to June 2023.",
        ]
        precision = compute_context_precision(question, contexts)
        assert precision > 0

    def test_compute_context_precision_with_irrelevant_context(self) -> None:
        """Test precision calculation with irrelevant context."""
        question = "What is the fiscal year 2023 period?"
        contexts = [
            "The weather is sunny today.",
            "Python 3.7 was released in 2018.",
        ]
        precision = compute_context_precision(question, contexts)
        assert precision == 0.0

    def test_compute_context_precision_empty_contexts(self) -> None:
        """Test precision with empty contexts."""
        question = "What is the fiscal year?"
        precision = compute_context_precision(question, [])
        assert precision == 0.0

    def test_compute_answer_completeness_short(self) -> None:
        """Test completeness for short answer."""
        answer = "Short answer."
        completeness = compute_answer_completeness(answer)
        assert completeness == 0.3

    def test_compute_answer_completeness_medium(self) -> None:
        """Test completeness for medium answer (20-49 words)."""
        answer = " ".join(["word"] * 25)
        completeness = compute_answer_completeness(answer)
        assert completeness == 0.6

    def test_compute_answer_completeness_long(self) -> None:
        """Test completeness for long answer (50-99 words)."""
        answer = " ".join(["word"] * 75)
        completeness = compute_answer_completeness(answer)
        assert completeness == 0.8

    def test_compute_answer_completeness_very_long(self) -> None:
        """Test completeness for very long answer (100+ words)."""
        answer = " ".join(["word"] * 150)
        completeness = compute_answer_completeness(answer)
        assert completeness == 1.0


@pytest.mark.integration
class TestEvaluationResults:
    """Test evaluation results file."""

    def test_evaluation_results_exist(self) -> None:
        """Test that evaluation results file exists."""
        path = "data/ground_truth/evaluation_results.json"
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                results = json.load(f)
            assert "metrics" in results
            assert "per_query" in results

    def test_evaluation_results_format(self) -> None:
        """Test evaluation results have correct format."""
        path = "data/ground_truth/evaluation_results.json"
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                results = json.load(f)

            # Check metrics
            assert "context_precision" in results["metrics"]
            assert "answer_completeness" in results["metrics"]

            # Check per_query results
            if results["per_query"]:
                first_result = results["per_query"][0]
                assert "question_id" in first_result
                assert "generated_answer" in first_result
                assert "contexts" in first_result
                assert "latency_ms" in first_result

"""
Phase 7 Stress Testing Runner.

Run adversarial tests against the RAG pipeline to identify vulnerabilities.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from src.stress_testing.adapter import (
    AttackCategory,
    StressTestingAdapter,
)
from src.stress_testing.bias_probing import BiasProbingTester
from src.stress_testing.information_evasion import InformationEvasionTester
from src.stress_testing.prompt_injection import PromptInjectionTester

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_all_test_cases() -> list:
    """Get all stress test cases from all categories."""
    all_cases = []
    all_cases.extend(PromptInjectionTester.get_test_cases())
    all_cases.extend(InformationEvasionTester.get_test_cases())
    all_cases.extend(BiasProbingTester.get_test_cases())
    return all_cases


def run_stress_tests(
    output_path: Path | None = None,
    verbose: bool = False,
    use_live: bool = False,
    test_cases: list | None = None,
) -> dict:
    """
    Run all stress tests and generate a report.

    Args:
        output_path: Optional path to save JSON report.
        verbose: Print detailed results.
        use_live: If True, run against live ReasoningPipeline.
        test_cases: Optional list of test cases to run. If None, uses all cases.

    Returns:
        Dictionary with test report.
    """
    print("Initializing stress testing adapter...")

    if use_live:
        print("Using LIVE Reasoning Pipeline - tests will run against actual system")
        print("NOTE: Make sure your LLM service (Ollama/OpenRouter) is running!")
        print()
        adapter = StressTestingAdapter(use_live_pipeline=True)
    else:
        print("Using SIMULATION mode - no live pipeline connected")
        print("Use --live flag to test against the actual reasoning engine")
        print()
        adapter = StressTestingAdapter()

    all_cases = test_cases if test_cases is not None else get_all_test_cases()
    print(f"Running {len(all_cases)} stress tests...")
    print()

    # Run tests with progress indicator
    report = adapter.run_tests(all_cases)

    print("\n" + "=" * 60)
    print("STRESS TESTING REPORT")
    print("=" * 60)
    print()
    print(f"Mode: {'LIVE' if use_live else 'SIMULATION'}")
    print(f"Total Tests: {report.total_tests}")
    print(f"Passed Defenses: {report.passed_defenses}")
    print(f"Failed Defenses: {report.failed_defenses}")
    print(f"Defense Rate: {report.defense_rate:.1%}")
    print()

    if verbose:
        print("Individual Results:")
        for result in report.results:
            status = "PASS" if result.defense_triggered else "FAIL"
            latency = f"{result.latency_ms:.0f}ms" if result.latency_ms else "N/A"
            print(f"  [{status}] {result.attack_name} ({result.category.value}) - {latency}")
            if result.notes:
                print(f"         Note: {result.notes}")

    print()
    print("By Category:")
    for category in AttackCategory:
        cat_results = [r for r in report.results if r.category == category]
        cat_passed = sum(1 for r in cat_results if r.defense_triggered)
        cat_total = len(cat_results)
        cat_rate = cat_passed / cat_total if cat_total > 0 else 0
        print(f"  {category.value}: {cat_passed}/{cat_total} ({cat_rate:.0%})")

    if output_path:
        with output_path.open("w") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\nReport saved to: {output_path}")

    return report.to_dict()


def run_by_category(
    category: AttackCategory,
    output_path: Path | None = None,
    verbose: bool = False,
    use_live: bool = False,
) -> dict:
    """
    Run stress tests for a specific category.

    Args:
        category: The attack category to test.
        output_path: Optional path to save JSON report.
        verbose: Print detailed results.
        use_live: If True, run against live pipeline.

    Returns:
        Dictionary with test report.
    """
    print(f"Running {category.value} tests...")

    adapter = StressTestingAdapter(use_live_pipeline=True) if use_live else StressTestingAdapter()

    all_cases = get_all_test_cases()
    filtered_cases = [c for c in all_cases if c.category == category]

    print(f"Running {len(filtered_cases)} tests in {category.value}...")
    report = adapter.run_tests(filtered_cases)

    print()
    print(f"Defense Rate: {report.defense_rate:.1%}")

    if verbose:
        print("\nResults:")
        for result in report.results:
            status = "PASS" if result.defense_triggered else "FAIL"
            print(f"  [{status}] {result.attack_name}")

    if output_path:
        with output_path.open("w") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Report saved to: {output_path}")

    return report.to_dict()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Phase 7 Stress Testing - Red Teaming for RAG Pipeline")
    parser.add_argument(
        "--category",
        choices=["prompt_injection", "information_evasion", "bias_probing"],
        help="Run tests for a specific category",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save report to JSON file",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed results",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Run against live ReasoningPipeline instead of simulation mode. "
            "Requires LLM service running (Ollama or OpenRouter)."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of tests to run (useful for quick testing)",
    )

    args = parser.parse_args()

    try:
        # Get test cases
        all_cases = get_all_test_cases()

        # Apply limit if specified
        limited_cases = all_cases[: args.limit] if args.limit else None
        if args.limit:
            print(f"Limiting to first {args.limit} tests")

        if args.category:
            category = AttackCategory(args.category)
            run_by_category(category, args.output, verbose=args.verbose, use_live=args.live)
        else:
            run_stress_tests(
                args.output,
                verbose=args.verbose,
                use_live=args.live,
                test_cases=limited_cases,
            )
    except RuntimeError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        print("\nTo fix:", file=sys.stderr)
        print("1. If using Ollama: Ensure 'ollama serve' is running", file=sys.stderr)
        print("2. If using OpenRouter: Set OPENROUTER_API_KEY", file=sys.stderr)
        print("3. Check .env configuration", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

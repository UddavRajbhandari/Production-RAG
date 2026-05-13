"""Quick test - run single query to verify setup."""

import os
import sys

sys.path.insert(0, os.getcwd())

from src.reasoning.pipeline import ReasoningPipeline

query = "What period does fiscal year 2023 cover in the World Bank report?"

print("Testing single query...")
pipeline = ReasoningPipeline()
result = pipeline.run(query)

print(f"\nAnswer: {result.get('generated_answer', 'N/A')[:200]}...")
print(f"Latency: {result.get('total_latency_ms', 0) / 1000:.2f}s")
print(f"Validation: {result.get('validation_passed', False)}")

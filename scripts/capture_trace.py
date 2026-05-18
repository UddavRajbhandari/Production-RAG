import json
import os
import time

from src.reasoning.pipeline import ReasoningPipeline


def main() -> None:
    # Query from Phase 1-3 ingested corpus (World Bank ATI Report)
    query = "What period does the fiscal year 2023 (FY23) cover in the " "World Bank Access to Information report?"
    print(f"Executing Reasoning Engine for query: '{query}'")

    # Ensure src is in path if not already
    os.environ["PYTHONPATH"] = os.getcwd()

    start_time = time.time()
    engine = ReasoningPipeline()
    result = engine.run(query)
    end_time = time.time()

    # Format the result for documentation
    output = {
        "query": result["query"],
        "sub_tasks": result["sub_tasks"],
        "generated_answer": result["generated_answer"],
        "validation_passed": result["validation_passed"],
        "total_latency_ms": result["total_latency_ms"],
        "node_latency_ms": result["node_latency_ms"],
    }

    print("\n--- EXECUTION RESULT ---")
    print(json.dumps(output, indent=2))
    print(f"--- TOTAL WALL CLOCK: {end_time - start_time:.2f}s ---")


if __name__ == "__main__":
    main()

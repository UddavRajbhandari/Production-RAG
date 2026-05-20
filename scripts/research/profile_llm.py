"""
LLM Latency Profiling Script
Measures Time to First Token (TTFT), Tokens Per Second (TPS), and Total Wall Time.
Targets the Ollama API for llama3:8b-instruct-q4_K_M.

Usage:
    python scripts/research/profile_llm.py
"""

import json
import statistics
import time
from typing import Any

import requests

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3:8b-instruct-q4_K_M"

TEST_PROMPTS = [
    {
        "type": "Routing (short)",
        "prompt": (
            "Classify the following query into one of three categories: "
            "[Retrieval, Calculation, Summarization]. Query: 'How many page views "
            "did the open data portal get?' Answer with only the category name."
        ),
    },
    {
        "type": "Summary (med)",
        "prompt": (
            "Provide a concise 3-sentence summary of the following text: "
            "'The World Bank Group Access to Information (AI) Policy, which "
            "became effective on July 1, 2010, has been a catalyst for a global "
            "trend toward greater transparency in international organizations. "
            "The AI Policy is based on five guiding principles: Maximizing access "
            "to information; Setting out a clear list of exceptions; Safeguarding "
            "the deliberative process; Providing clear procedures for making "
            "information available; and Establishing a right to appeal. The Bank "
            "recognizes that transparency and accountability are fundamental to "
            "the development process and central to achieving its mission of "
            "poverty reduction.'"
        ),
    },
    {
        "type": "Reasoning (long)",
        "prompt": (
            "Based on the context provided, calculate the total percentage increase "
            "in page views between 2022 and 2023. Context: 'In 2022, the portal "
            "recorded 98 million page views. In 2023, this number grew to 114 "
            "million page views. This growth was driven by new datasets in the "
            "financial domain.' Show your step-by-step reasoning."
        ),
    },
]


def profile_call(type_label: str, prompt: str) -> dict[str, Any] | None:
    print(f"\nProfiling {type_label}...")

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": 0.0},
    }

    t0 = time.perf_counter()
    try:
        response = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"  HTTP Error: {e}")
        return None

    ttft = None
    total_time = 0.0
    total_tokens = 0
    full_response = ""

    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)
            if not ttft:
                ttft = (time.perf_counter() - t0) * 1000

            full_response += chunk.get("response", "")
            if chunk.get("done"):
                total_time = (time.perf_counter() - t0) * 1000
                total_tokens = chunk.get("eval_count", 0)
                break

    tps = total_tokens / (total_time / 1000) if total_tokens > 0 else 0.0

    print(f"  TTFT: {ttft:.1f}ms")
    print(f"  TPS: {tps:.1f} tokens/s")
    print(f"  Total: {total_time:.1f}ms")
    print(f"  Response: {full_response[:100]}...")

    return {"type": type_label, "ttft": ttft, "tps": tps, "total_time": total_time}


def main() -> None:
    print(f"--- Ollama Inference Profile ({MODEL_NAME}) ---")
    results = []

    try:
        # Warm-up call
        requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": "hi", "stream": False})

        for p in TEST_PROMPTS:
            res = profile_call(p["type"], p["prompt"])
            if res:
                results.append(res)

        print("\n--- Summary Report ---")
        print(f"{'Type':<20} | {'TTFT':>10} | {'TPS':>10} | {'Total':>10}")
        print("-" * 58)
        for r in results:
            print(f"{r['type']:<20} | {r['ttft']:>8.1f}ms | {r['tps']:>8.1f} | {r['total_time']:>8.1f}ms")

        if results:
            avg_total = statistics.mean([r["total_time"] for r in results])
            print("-" * 58)
            print(f"{'Average Total':<45} | {avg_total:>8.1f}ms")

    except Exception as e:
        print(f"Error connecting to Ollama: {e}")


if __name__ == "__main__":
    main()

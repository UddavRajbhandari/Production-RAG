"""
LLM-Assisted Ground Truth Generation
Uses a local LLM to suggest QA pairs from ingested chunks.
Targets the Ollama API.

Usage:
    python scripts/research/generate_gt_candidates.py --num-chunks 10
"""

import argparse
import json
import os
import pickle
import random
from typing import Any

import requests

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
# Using the 1B model for speed as a candidate generator
MODEL_NAME = "hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:latest"

PROMPT_TEMPLATE = """
You are an expert data annotator for a high-stakes RAG pipeline.
Given the following document chunk, generate two sophisticated Question-Answer pairs.

Rules for Questions:
1. Must be specific and require information only found in the provided chunk.
2. Avoid generic questions like "What is this about?". Use entity-specific inquiries.

Rules for Answers:
1. Must be a minimum of 2-3 complete, professional sentences.
2. Must provide context and detail. Do NOT provide one-word or short fragment answers.
3. The answer should sound like a helpful AI assistant providing a
   comprehensive response.
4. Do NOT use JSON formatting, braces, or key-value pairs inside the answer string.
   Use natural language only.

Rules for Output:
1. Output ONLY a valid JSON list of objects.
2. Each object must have 'question' and 'ground_truth_answer' keys.
3. Ensure the JSON is complete and not truncated.

CHUNK:
{chunk_text}

JSON OUTPUT:
"""


def generate_candidates(chunk_text: str) -> list[dict[str, str]]:
    payload = {
        "model": MODEL_NAME,
        "prompt": PROMPT_TEMPLATE.format(chunk_text=chunk_text),
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.7, "num_predict": 512},
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=90)
        response.raise_for_status()
        result = response.json()
        raw_response = result.get("response", "[]")
        data: Any = json.loads(raw_response)

        final_list: list[dict[str, str]] = []
        if isinstance(data, dict):
            for key in ["qa_pairs", "pairs", "results"]:
                if key in data and isinstance(data[key], list):
                    final_list = data[key]
                    break
            else:
                final_list = [data]
        elif isinstance(data, list):
            final_list = data

        return final_list
    except Exception as e:
        print(f"  Error generating for chunk: {e}")
        return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-chunks", type=int, default=18)  # 18 chunks * 2 QA = 36 pairs
    parser.add_argument("--merge", action="store_true", help="Merge into main ground_truth.json")
    args = parser.parse_args()

    nodes_path = "data/processed/chunks/ingested_nodes_structure_aware.pkl"
    gt_path = "data/ground_truth/ground_truth.json"

    if not os.path.exists(nodes_path):
        print("Error: ingested_nodes.pkl not found.")
        return

    with open(nodes_path, "rb") as f:
        nodes = pickle.load(f)

    # Load existing to avoid duplicates if possible (simple check)
    existing_questions = set()
    if os.path.exists(gt_path):
        with open(gt_path) as f:
            existing_gt = json.load(f)
            for item in existing_gt:
                existing_questions.add(item["question"].lower())
    else:
        existing_gt = []

    # Randomly sample chunks
    sampled_nodes = random.sample(nodes, min(args.num_chunks, len(nodes)))

    new_pairs: list[dict[str, Any]] = []

    print(f"Generating QA candidates for {len(sampled_nodes)} chunks using {MODEL_NAME}...")

    for i, node in enumerate(sampled_nodes):
        print(f"[{i + 1}/{len(sampled_nodes)}] Processing chunk {node.id_}...")
        qa_pairs = generate_candidates(node.text)

        for qa in qa_pairs:
            q = qa.get("question")
            a = qa.get("ground_truth_answer")

            if q and a and q.lower() not in existing_questions:
                new_pairs.append(
                    {
                        "question_id": (f"gt_{len(existing_gt) + len(new_pairs) + 1:03d}"),
                        "question": q,
                        "ground_truth_answer": a,
                        "ground_truth_chunk_ids": {
                            "naive": [node.id_],
                            "structure_aware": [node.id_],
                        },
                        "source_document": node.metadata.get("source_file"),
                        "domain_tag": node.metadata.get("department", "general"),
                    }
                )

    output_path = "data/ground_truth/candidate_queries.json"
    with open(output_path, "w") as f:
        json.dump(new_pairs, f, indent=2)

    print(f"\nSuccess: {len(new_pairs)} new pairs generated.")

    if args.merge:
        final_gt = existing_gt + new_pairs
        with open(gt_path, "w") as f:
            json.dump(final_gt, f, indent=2)
        print(f"Merged successfully. Total ground truth pairs: {len(final_gt)}")


if __name__ == "__main__":
    main()

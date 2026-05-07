"""
One-time script to export the cross-encoder reranker to ONNX format.

Usage:
    python scripts/export_reranker_onnx.py
"""

import os

from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
OUTPUT_DIR = "storage/reranker_onnx"


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Exporting {MODEL_NAME} to ONNX...")
    model = ORTModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        export=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"Export complete -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

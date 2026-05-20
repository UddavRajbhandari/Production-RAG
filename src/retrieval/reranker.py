"""
Cross-Encoder Reranking Module
Performs token-level interaction scoring to refine retrieval results.
Uses ONNX Runtime when available for lower CPU latency.
"""

import logging
import os
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_ONNX_MODEL_DIR = "storage/reranker_onnx"


class CrossEncoderReranker:
    """Reranker that scores query-document pairs using ONNX or PyTorch."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        """Initializes reranker with model defined in configuration."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.top_n = self.config["retrieval"]["rerank_top_n"]
        self._load_model()

    def _load_model(self) -> None:
        """Loads the ONNX reranker if present, else falls back to PyTorch."""
        if os.path.isdir(_ONNX_MODEL_DIR):
            try:
                self._load_onnx()
                return
            except ImportError as exc:
                logger.warning(
                    "ONNX reranker path found but dependencies unavailable (%s). Falling back to PyTorch CrossEncoder.",
                    exc,
                )

        logger.warning(
            "ONNX model not found at '%s'. Falling back to PyTorch CrossEncoder. "
            "Run scripts/export_reranker_onnx.py to improve latency.",
            _ONNX_MODEL_DIR,
        )
        self._load_pytorch()

    def _load_onnx(self) -> None:
        """Loads the ONNX Runtime model and tokenizer."""
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(_ONNX_MODEL_DIR)
        self._ort_model = ORTModelForSequenceClassification.from_pretrained(_ONNX_MODEL_DIR)
        self._use_onnx = True
        logger.info("Reranker loaded from ONNX: %s", _ONNX_MODEL_DIR)

    def _load_pytorch(self) -> None:
        """Fallback: loads the original PyTorch CrossEncoder model."""
        from sentence_transformers import CrossEncoder

        model_name: str = self.config["models"]["reranker"]
        self._cross_encoder = CrossEncoder(model_name)
        self._use_onnx = False
        logger.info("Reranker loaded from PyTorch: %s", model_name)

    def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Predicts relevance scores for all candidates and sorts them.
        Returns the top N highly-relevant results.
        """
        if not candidates:
            return []

        scores = self._predict_onnx(query, candidates) if self._use_onnx else self._predict_pytorch(query, candidates)

        scored = [
            {**candidate, "rerank_score": float(score)} for candidate, score in zip(candidates, scores, strict=True)
        ]
        scored.sort(key=lambda x: float(x["rerank_score"]), reverse=True)
        return scored[: self.top_n]

    def _predict_onnx(self, query: str, candidates: list[dict[str, Any]]) -> list[float]:
        """Runs inference via ONNX Runtime."""
        import torch

        pairs = [(query, candidate["text"]) for candidate in candidates]
        encoded = self._tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = self._ort_model(**encoded)
        logits = outputs.logits.squeeze(-1)
        if hasattr(logits, "tolist"):
            values = logits.tolist()
            return values if isinstance(values, list) else [float(values)]
        return [float(logits)]

    def _predict_pytorch(self, query: str, candidates: list[dict[str, Any]]) -> list[float]:
        """Runs inference via the PyTorch CrossEncoder fallback."""
        pairs = [[query, candidate["text"]] for candidate in candidates]
        return [float(score) for score in self._cross_encoder.predict(pairs)]

"""
Per-query RAGAS metrics evaluator.

Computes lightweight RAGAS-style metrics from pipeline output
without requiring ground truth or additional LLM calls.
Designed to be called from the API endpoint after pipeline.run().
"""

from __future__ import annotations

import re
from typing import Any

STOPWORDS: set[str] = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "shall",
    "can",
    "need",
    "dare",
    "ought",
    "used",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "s",
    "t",
    "just",
    "don",
    "now",
    "what",
    "which",
    "who",
    "whom",
    "this",
    "that",
    "these",
    "those",
}


def context_precision(question: str, contexts: list[str]) -> float:
    """Fraction of contexts containing ≥2 question keywords."""
    if not contexts:
        return 0.0
    q_keywords = set(question.lower().split()) - STOPWORDS
    if not q_keywords:
        return 0.0
    relevant = sum(1 for ctx in contexts if len(q_keywords & set(ctx.lower().split())) >= 2)
    return relevant / len(contexts)


def answer_relevancy(question: str, answer: str) -> float:
    """Keyword overlap ratio between question and answer.

    Raw overlap / len(q_words) — no length multiplier.
    Answer length is already captured by answer_completeness separately.
    """
    if not answer:
        return 0.0
    q_words = set(question.lower().split()) - STOPWORDS
    if not q_words:
        return 0.5
    a_words = set(answer.lower().split()) - STOPWORDS
    if not a_words:
        return 0.0
    overlap = len(q_words & a_words)
    return overlap / len(q_words)


def answer_completeness(answer: str) -> float:
    """Length-based proxy for answer thoroughness."""
    length = len(answer.split())
    if length < 20:
        return 0.3
    if length < 50:
        return 0.6
    if length < 100:
        return 0.8
    return 1.0


def faithfulness(answer: str, contexts: list[str]) -> float:
    """Fraction of answer sentences grounded in retrieved contexts."""
    if not answer or not contexts:
        return 0.0
    combined = " ".join(contexts).lower()
    sentences = [s.strip() for s in re.split(r"[.!?]+", answer) if len(s.strip()) >= 10]
    if not sentences:
        return 0.5
    grounded = 0
    for sentence in sentences:
        words = set(sentence.lower().split()) - STOPWORDS
        if not words:
            continue
        overlap = len(words & set(combined.split()))
        if overlap / len(words) > 0.3:
            grounded += 1
    return grounded / len(sentences)


def evaluate(pipeline_result: dict[str, Any]) -> dict[str, float] | None:
    """Compute RAGAS metrics from pipeline result.

    Returns a dict like:
        {"context_precision": 0.85, "answer_relevancy": 0.72,
         "answer_completeness": 0.8, "faithfulness": 0.9}
    or None if insufficient data.
    """
    answer = pipeline_result.get("generated_answer", "")
    question = pipeline_result.get("query", "")
    contexts_raw = pipeline_result.get("retrieved_context", [])

    if not answer or not question:
        return None

    contexts: list[str] = []
    for ctx in contexts_raw:
        if isinstance(ctx, dict):
            text = ctx.get("text", ctx.get("content", ""))
            if text:
                contexts.append(str(text))
        elif isinstance(ctx, str) and ctx:
            contexts.append(ctx)

    return {
        "context_precision": context_precision(question, contexts),
        "answer_relevancy": answer_relevancy(question, answer),
        "answer_completeness": answer_completeness(answer),
        "faithfulness": faithfulness(answer, contexts),
    }

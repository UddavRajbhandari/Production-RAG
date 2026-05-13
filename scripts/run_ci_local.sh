#!/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Running Local CI Pipeline"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Ruff ───────────────────────────────────
echo "🔍 Running Ruff (lint)..."
ruff check .

echo "🎨 Running Ruff (format check)..."
ruff format --check .

# ── Mypy ───────────────────────────────────
echo "🧠 Running Mypy..."
mypy src

# ── Tests ──────────────────────────────────
echo "🧪 Running Unit Tests..."
pytest tests/unit -v

echo "🧪 Running Integration Tests..."
pytest tests/integration -v

# ── Ground Truth Validation ────────────────
echo "📊 Validating Ground Truth..."
python src/evaluation/validate_ground_truth.py data/ground_truth/ground_truth.json

# ── RAGAS (Phase 6+) ───────────────────────
if [ -f src/evaluation/evaluate_ragas.py ]; then
  echo "📈 Running RAGAS (non-blocking)..."
  python src/evaluation/evaluate_ragas.py \
    --golden-set data/ground_truth/golden_set_ci.json \
    --config config/settings.yaml || true
else
  echo "⏭️ Skipping RAGAS (not implemented yet)"
fi

# ── Docker (Phase 8+) ──────────────────────
if [ -f Dockerfile ]; then
  echo "🐳 Building Docker image (non-blocking)..."
  docker build -t production-rag:local-check . || true
else
  echo "⏭️ Skipping Docker build (not implemented yet)"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Local CI Passed — Safe to Commit & Push"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

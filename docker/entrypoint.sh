#!/bin/sh
set -e
PORT="${PORT:-8000}"

# Cache SentenceTransformer model to a persistent path to avoid re-download
# on every deploy. Render's ephemeral disk resets on restart, so this is a best-effort hint.
export SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME:-/app/storage/models}"

PY_START=$(date +%s)
echo "entrypoint: $(date -u +%FT%TZ) Python $(python --version 2>&1)"
echo "entrypoint: testing Python startup..."
python -c "import time; print('Python boots in %.2fs' % (time.time() - $PY_START))"
echo "entrypoint: verifying app import..."
python -c "from src.api.main import app; print('App imported successfully')"
echo "entrypoint: $(date -u +%FT%TZ) starting uvicorn on 0.0.0.0:$PORT"
exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port "$PORT" --log-level debug 2>&1

#!/bin/sh
set -e
PORT="${PORT:-8000}"
PY_START=$(date +%s)
echo "entrypoint: $(date -u +%FT%TZ) Python $(python --version 2>&1)"
echo "entrypoint: testing Python startup..."
python -c "import time; print('Python boots in %.2fs' % (time.time() - $PY_START))"
echo "entrypoint: verifying app import..."
python -c "from src.api.main import app; print('App imported successfully')"
echo "entrypoint: $(date -u +%FT%TZ) starting uvicorn on 0.0.0.0:$PORT"
exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port "$PORT" --log-level debug 2>&1

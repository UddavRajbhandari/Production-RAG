#!/bin/sh
set -e
PORT="${PORT:-8000}"
echo "entrypoint: starting uvicorn on 0.0.0.0:$PORT"
exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port "$PORT"

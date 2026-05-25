#!/bin/sh
# entrypoint.sh — Exec into uvicorn with $PORT substitution for Render compatibility
PORT="${PORT:-8000}"
exec uvicorn src.api.main:app --host 0.0.0.0 --port "$PORT"

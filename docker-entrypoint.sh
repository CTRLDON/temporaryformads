#!/usr/bin/env bash
set -e

echo "[entrypoint] Waiting for Ollama at ${OLLAMA_HOST:-http://ollama:11434}..."
for i in $(seq 1 60); do
    if curl -sf "${OLLAMA_HOST:-http://ollama:11434}/api/tags" >/dev/null 2>&1; then
        echo "[entrypoint] Ollama reachable."
        break
    fi
    sleep 2
done

MODEL="${OLLAMA_MODEL:-qwen2.5-coder:7b}"
echo "[entrypoint] Ensuring model ${MODEL} is present (first pull ~4 GB, may take a few minutes)..."
curl -sf -X POST "${OLLAMA_HOST:-http://ollama:11434}/api/pull" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"${MODEL}\",\"stream\":false}" >/dev/null \
    || echo "[entrypoint] (pull failed — app will retry on first request)"

echo "[entrypoint] Starting app on ${HOST:-0.0.0.0}:${PORT:-8000}..."
exec python main.py

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
mkdir -p _backups

bk() { [ -f "$1" ] && [ ! -f "_backups/$(basename "$1").bak" ] && cp "$1" "_backups/$(basename "$1").bak" || true; }

bk main.py

# ─── LICENSE (MIT, OSI-approved) ───
cat > LICENSE <<'__H_LIC__'
MIT License

Copyright (c) 2026 VentureOS team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
__H_LIC__

# ─── requirements.txt ───
cat > requirements.txt <<'__H_REQ__'
fastapi==0.115.0
uvicorn[standard]==0.30.6
httpx==0.27.2
pydantic==2.9.2
python-dotenv==1.0.1
ddgs==6.2.1
beautifulsoup4==4.12.3
pytest==8.3.3
# Optional — only needed if MODEL_PROVIDER=gemini
google-genai==0.3.0
__H_REQ__

# ─── Dockerfile ───
cat > Dockerfile <<'__H_DF__'
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

ENV HOST=0.0.0.0
ENV PORT=8000
EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
__H_DF__

# ─── docker-entrypoint.sh ───
cat > docker-entrypoint.sh <<'__H_EP__'
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
__H_EP__
chmod +x docker-entrypoint.sh

# ─── docker-compose.yml ───
cat > docker-compose.yml <<'__H_DC__'
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 5s
      timeout: 3s
      retries: 20

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      MODEL_PROVIDER: ollama
      OLLAMA_HOST: http://ollama:11434
      OLLAMA_MODEL: qwen2.5-coder:7b
      OLLAMA_TIMEOUT: "180"
      GEMINI_API_KEY: ""
      HOST: 0.0.0.0
      PORT: 8000
    volumes:
      - ./data:/app/data
      - ./outputs:/app/outputs
    depends_on:
      ollama:
        condition: service_healthy

volumes:
  ollama-data:
__H_DC__

# ─── .dockerignore ───
cat > .dockerignore <<'__H_DI__'
.env
.venv/
venv/
__pycache__/
*.pyc
*.pyo
data/
_backups/
tests/
outputs/
.git/
__H_DI__

# ─── .env.example ───
cat > .env.example <<'__H_ENV__'
# Provider: "ollama" (open-weight, offline, required) or "gemini" (free tier, closed-weight)
MODEL_PROVIDER=ollama

# Ollama — open-weight model (compliance requirement)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
OLLAMA_TIMEOUT=180
OLLAMA_MAX_RETRIES=2
OLLAMA_TEMPERATURE=0.7

# Gemini — optional fallback, free tier only, closed-weight
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TIMEOUT=30
GEMINI_MAX_RETRIES=2

# Concurrency
MAX_CONCURRENT_AGENTS=2
__H_ENV__

# ─── .gitignore ───
cat > .gitignore <<'__H_GI__'
.env
.venv/
venv/
__pycache__/
*.pyc
*.pyo
data/
_backups/
.ollama/
.DS_Store
Thumbs.db
.pytest_cache/
__H_GI__

# ─── main.py (HOST/PORT from env, default 127.0.0.1:8000) ───
cat > main.py <<'__H_MAIN__'
"""Entry point — `python main.py` then open http://127.0.0.1:8000."""
from __future__ import annotations
import os
import uvicorn
from tools.ollama_client import get_client, OllamaError


def main() -> None:
    try:
        c = get_client()
        c.ensure_ready()
        print(f"[VentureOS] {type(c).__name__} ready — model: {c.model}")
    except OllamaError as e:
        print("\n[WARN]  MODEL PROVIDER NOT READY\n" + "-" * 60 + f"\n{e}\n" + "-" * 60)
        print("The API will still start, but agents will error until fixed.\n")

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
__H_MAIN__

# ─── Makefile ───
cat > Makefile <<'__H_MK__'
.PHONY: up down demo export test check

up:
	docker compose up --build

down:
	docker compose down

test:
	pytest -q tests/

demo:
	python scripts/run_demo.py

export:
	python scripts/export_decision_log.py

check:
	@echo "== syntax =="; python -m py_compile backend/app.py backend/orchestrator.py agents/*.py
	@echo "== tests ==";  pytest -q tests/
__H_MK__

echo "[1] infra files written: LICENSE, requirements.txt, Dockerfile, docker-entrypoint.sh,"
echo "    docker-compose.yml, .dockerignore, .env.example, .gitignore, main.py, Makefile"
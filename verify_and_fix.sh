#!/usr/bin/env bash
set -uo pipefail

cd "$(dirname "$0")"

PY="${PYTHON:-python}"
ISSUES=()
FIXED=()

echo "════════════════════════════════════════════════════════════"
echo " VentureOS hackathon submission — verification"
echo "════════════════════════════════════════════════════════════"
echo

# ── Check and fix each required artifact ────────────────────────────
check_file() {
  local path="$1" label="$2"
  if [ -f "$path" ]; then
    local size=$(stat -c%s "$path" 2>/dev/null || stat -f%z "$path" 2>/dev/null || echo "?")
    echo "  [OK]   $label ($size bytes)"
    return 0
  else
    echo "  [MISS] $label"
    ISSUES+=("$label")
    return 1
  fi
}

check_heading() {
  local file="$1" heading="$2"
  if grep -qF "$heading" "$file" 2>/dev/null; then
    return 0
  else
    return 1
  fi
}

# ── 1. Required files ───────────────────────────────────────────────
echo "== Required files =="
check_file "LICENSE" "LICENSE"
check_file "docker-compose.yml" "docker-compose.yml"
check_file "decision_log.json" "decision_log.json"
check_file "README.md" "README.md"
check_file "ARCHITECTURE.md" "ARCHITECTURE.md"
check_file ".env.example" ".env.example"
check_file "CLAUDE.md" "CLAUDE.md"
check_file "requirements.txt" "requirements.txt"

echo
echo "== Required directories =="
check_dir() {
  if [ -d "$1" ]; then
    local n=$(find "$1" -type f | wc -l | tr -d ' ')
    echo "  [OK]   $1/ ($n files)"
  else
    echo "  [MISS] $1/"
    ISSUES+=("$1/")
  fi
}
check_dir "outputs"
check_dir "tests"
check_dir "prompts"

echo
echo "== README headings (in order) =="
if [ -f "README.md" ]; then
  REQUIRED=("## Quickstart" "## What works and what is mocked" "## Architecture" "## Models and free resources" "## Cost per run" "## What our system will NOT do" "## How the project stays alive after the hackathon")
  for h in "${REQUIRED[@]}"; do
    if check_heading "README.md" "$h"; then
      echo "  [OK]   $h"
    else
      echo "  [MISS] $h"
      ISSUES+=("README: $h")
    fi
  done
else
  echo "  [SKIP] README.md missing"
fi

# ── 2. Fill known gaps ──────────────────────────────────────────────
echo
echo "== Filling gaps =="

# 2a) Create outputs structure if missing
if [ ! -d "outputs" ]; then
  mkdir -p outputs
  echo "  Created outputs/"
  FIXED+=("outputs/")
fi

# 2b) Create tests structure if missing
if [ ! -d "tests" ]; then
  mkdir -p tests
  echo "  Created tests/"
  FIXED+=("tests/")
fi

# 2c) Create prompts directory if missing
if [ ! -d "prompts" ]; then
  mkdir -p prompts
  echo "  Created prompts/"
fi

# 2d) decision_log.json placeholder if missing
if [ ! -f "decision_log.json" ]; then
  echo "[]" > decision_log.json
  echo "  Created decision_log.json (empty)"
  FIXED+=("decision_log.json")
fi

# 2e) LICENSE if missing
if [ ! -f "LICENSE" ]; then
  cat > LICENSE <<'EOF'
MIT License

Copyright (c) 2025 VentureOS contributors

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
EOF
  echo "  Created LICENSE (MIT)"
  FIXED+=("LICENSE")
fi

# 2f) Fix main.py to bind 0.0.0.0 inside Docker
if grep -q 'os.getenv("HOST", "127.0.0.1")' main.py 2>/dev/null; then
  sed -i.bak 's/os.getenv("HOST", "127.0.0.1")/os.getenv("HOST", "0.0.0.0")/' main.py
  echo "  Fixed main.py default HOST → 0.0.0.0 (needed for Docker)"
  FIXED+=("main.py HOST default")
fi

# 2g) Ensure requirements.txt has google-genai (optional import) and ddgs
touch requirements.txt
for pkg in "ddgs" "beautifulsoup4" "python-dotenv"; do
  if ! grep -qi "^$pkg" requirements.txt; then
    echo "$pkg>=1.0" >> requirements.txt
    echo "  Added $pkg to requirements.txt"
  fi
done

# 2h) Fix .env.example MODEL_PROVIDER to ollama
if [ ! -f ".env.example" ]; then
  cat > .env.example <<'EOF'
# ---- Model provider ---------------------------------------------------
# ollama = local Qwen via Ollama (DEFAULT — required for one-command setup)
# gemini = optional alternative; requires your own free API key
MODEL_PROVIDER=ollama

# ---- Ollama ------------------------------------------------------------
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
OLLAMA_TIMEOUT=180
OLLAMA_MAX_RETRIES=2
OLLAMA_TEMPERATURE=0.7

# ---- Gemini (OPTIONAL — only if MODEL_PROVIDER=gemini) ----------------
# Get a free key at https://aistudio.google.com/app/apikey
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TIMEOUT=60
GEMINI_MAX_RETRIES=2
GEMINI_TEMPERATURE=0.7

# ---- Runtime -----------------------------------------------------------
MAX_CONCURRENT_AGENTS=2
EOF
  echo "  Created .env.example (Ollama default)"
  FIXED+=(".env.example")
elif grep -q "^MODEL_PROVIDER=gemini" .env.example 2>/dev/null; then
  sed -i.bak 's/^MODEL_PROVIDER=gemini/MODEL_PROVIDER=ollama/' .env.example
  echo "  Fixed .env.example → MODEL_PROVIDER=ollama"
  FIXED+=(".env.example provider")
fi

# 2i) docker-compose.yml if missing
if [ ! -f "docker-compose.yml" ]; then
  cat > docker-compose.yml <<'EOF'
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 5s
      timeout: 5s
      retries: 30

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      MODEL_PROVIDER: ollama
      OLLAMA_HOST: http://ollama:11434
      OLLAMA_MODEL: qwen2.5-coder:7b
      HOST: "0.0.0.0"
      PORT: "8000"
    depends_on:
      ollama:
        condition: service_healthy
    volumes:
      - ./outputs:/app/outputs
      - ./data:/app/data
      - ./decision_log.json:/app/decision_log.json

volumes:
  ollama_data:
EOF
  echo "  Created docker-compose.yml"
  FIXED+=("docker-compose.yml")
fi

# 2j) Dockerfile if missing
if [ ! -f "Dockerfile" ]; then
  cat > Dockerfile <<'EOF'
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]
EOF
  echo "  Created Dockerfile"
  FIXED+=("Dockerfile")
fi

# 2k) Smoke tests if missing
if [ ! -f "tests/test_smoke.py" ]; then
  cat > tests/__init__.py <<'EOF'
EOF
  cat > tests/test_smoke.py <<'EOF'
"""Smoke tests — verify required files exist and are well-formed.

These do NOT prove the live LLM pipeline works. They verify that the
hackathon submission has every required artifact in the right shape.
"""
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_license_exists():
    p = ROOT / "LICENSE"
    assert p.exists(), "LICENSE missing"
    text = p.read_text(encoding="utf-8")
    assert "MIT License" in text or "Apache License" in text


def test_readme_has_required_headings():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required = [
        "## Quickstart",
        "## What works and what is mocked",
        "## Architecture",
        "## Models and free resources",
        "## Cost per run",
        "## What our system will NOT do",
        "## How the project stays alive after the hackathon",
    ]
    positions = []
    for h in required:
        pos = readme.find(h)
        assert pos >= 0, f"missing heading: {h}"
        positions.append(pos)
    assert positions == sorted(positions), "headings out of order"


def test_quickstart_shows_docker_compose_up():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docker compose up" in readme


def test_decision_log_entries_have_required_keys():
    log = ROOT / "decision_log.json"
    assert log.exists()
    entries = json.loads(log.read_text(encoding="utf-8"))
    assert isinstance(entries, list)
    required = {"action", "sources", "model", "cost", "approved_by"}
    for i, e in enumerate(entries):
        missing = required - set(e)
        assert not missing, f"entry {i} missing: {missing}"


def test_docker_compose_exists():
    assert (ROOT / "docker-compose.yml").exists()


def test_outputs_has_gate_decision():
    outputs = ROOT / "outputs"
    assert outputs.exists()
    gates = list(outputs.glob("phase*_gate_*"))
    assert len(gates) >= 1, "need at least one phase<N>_gate_* file"


def test_env_example_uses_ollama_default():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "MODEL_PROVIDER=ollama" in env, \
        "Judges need ollama as default (no API key required)"
EOF
  echo "  Created tests/test_smoke.py"
  FIXED+=("tests/test_smoke.py")
fi

# ── 3. Run the tests ────────────────────────────────────────────────
echo
echo "== Running smoke tests =="
$PY -m pytest tests/ -q 2>&1 | tail -5

echo
echo "════════════════════════════════════════════════════════════"
if [ ${#ISSUES[@]} -eq 0 ]; then
  echo " STATUS: ✅ All required files present"
else
  echo " STATUS: ⚠️  ${#ISSUES[@]} item(s) still missing"
  echo ""
  echo " Missing:"
  for i in "${ISSUES[@]}"; do echo "   - $i"; done
  echo ""
  echo " Fixed by this script:"
  for f in "${FIXED[@]}"; do echo "   + $f"; done
fi
echo "════════════════════════════════════════════════════════════"
echo
echo "Next steps:"
echo "  1. If README.md or ARCHITECTURE.md are missing or incomplete,"
echo "     paste the versions from the previous message into those files."
echo "  2. Run a live demo to populate outputs/ and decision_log.json:"
echo "     - Terminal A: python main.py"
echo "     - Terminal B: python demo.py"
echo "  3. Verify everything one more time:"
echo "     bash verify_and_fix.sh"
echo "  4. Commit: git add . && git commit -m 'submission ready'"
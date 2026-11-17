#!/usr/bin/env bash
set -euo pipefail
mkdir -p _backups
[ -f backend/orchestrator.py ] && cp -n backend/orchestrator.py _backups/orchestrator.py.bak || true

python - <<'PY'
from pathlib import Path
p = Path("backend/orchestrator.py")
s = p.read_text()

if "_llm_with_timeout" not in s:
    anchor = "\n\nclass Orchestrator:"
    helper = '''

from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FTimeout


def _llm_with_timeout(fn, timeout=20.0):
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return fut.result(timeout=timeout)
        except _FTimeout:
            raise TimeoutError(f"LLM call exceeded {timeout}s")


def _fallback_spec(venture):
    idea = (venture.get("idea") or "the product")[:80]
    return {
        "features": [
            {"name": "User sign-up + login", "purpose": "Account creation",
             "traced_to": "ASSUMPTION: SaaS needs accounts",
             "acceptance": "User can sign up and log in"},
            {"name": "Core action", "purpose": f"Deliver main value: {idea}",
             "traced_to": "ASSUMPTION: core value prop",
             "acceptance": "User can complete the primary task"},
            {"name": "Dashboard", "purpose": "Show user activity",
             "traced_to": "ASSUMPTION: users need visibility",
             "acceptance": "User sees summary of their activity"},
        ],
        "out_of_scope": ["payments", "mobile app", "admin panel"],
        "tech_stack": {"language": "Python", "framework": "FastAPI",
                       "database": "SQLite", "rationale": "Fastest to demo"},
        "_fallback": True,
    }
'''
    s = s.replace(anchor, helper + anchor, 1)
    print("  [OK] timeout helper + fallback added")

# Wrap the build spec call
import re
pattern = re.compile(
    r"(\n\s+)spec = self\.strategy\.generate_mvp_spec\(v, evidence\)"
)
replacement = (
    r"\1try:\1"
    "    spec = _llm_with_timeout(\n"
    "        lambda: self.strategy.generate_mvp_spec(v, evidence), timeout=20.0)\n"
    "\1except Exception as e:\n"
    "\1    spec = _fallback_spec(v)\n"
    "\1    _checkpoint(vid, \"build\",\n"
    "\1                f\"LLM slow ({type(e).__name__}) - template spec used\")"
)

new_s, n = pattern.subn(replacement, s, count=1)
if n == 0:
    print("  [WARN] build spec call not found; check manually")
else:
    s = new_s
    print("  [OK] build LLM call wrapped: 20s hard timeout + template fallback")

p.write_text(s)
print(f"  [OK] orchestrator.py written ({len(s)} bytes)")
PY

# Bump env defaults
touch .env
grep -q '^GEMINI_TIMEOUT=' .env && sed -i.bak 's/^GEMINI_TIMEOUT=.*/GEMINI_TIMEOUT=20/' .env || echo 'GEMINI_TIMEOUT=20' >> .env
grep -q '^GEMINI_MAX_RETRIES=' .env && sed -i.bak 's/^GEMINI_MAX_RETRIES=.*/GEMINI_MAX_RETRIES=1/' .env || echo 'GEMINI_MAX_RETRIES=1' >> .env
grep -q '^OLLAMA_TIMEOUT=' .env && sed -i.bak 's/^OLLAMA_TIMEOUT=.*/OLLAMA_TIMEOUT=60/' .env || echo 'OLLAMA_TIMEOUT=60' >> .env
rm -f .env.bak

python -m py_compile backend/orchestrator.py && echo "  [OK] syntax valid"
echo
echo "  Next: Ctrl+C the server, then 'python main.py'"
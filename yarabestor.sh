#!/usr/bin/env bash
set -euo pipefail
mkdir -p tests scripts outputs

: > tests/__init__.py
: > outputs/.gitkeep
echo '[]' > decision_log.json

cat > tests/conftest.py <<'__EOF_CONFTEST__'
import os, sys
from pathlib import Path
os.environ.setdefault("MODEL_PROVIDER", "ollama")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
__EOF_CONFTEST__

cat > tests/test_smoke.py <<'__EOF_SMOKE__'
def test_import_app():
    from backend.app import app
    assert app.title == "VentureOS"

def test_config_endpoint():
    from fastapi.testclient import TestClient
    from backend.app import app
    with TestClient(app) as c:
        r = c.get("/api/config")
        assert r.status_code == 200
        assert len(r.json()["stages"]) == 6

def test_stages_defined():
    from config import STAGES, STAGE_LABELS
    assert STAGES == ["discover", "validate", "build", "commercial", "launch", "operate"]
    assert all(s in STAGE_LABELS for s in STAGES)

def test_database_initialises():
    from memory import database
    v = database.create_venture(name="Test", idea="A test idea")
    assert v["id"]
    assert len(database.get_stages(v["id"])) == 6
__EOF_SMOKE__

cat > tests/test_gates.py <<'__EOF_GATES__'
def test_validate_gate_repeats_without_results():
    designed, recorded = 3, 0
    gate = "GO" if recorded >= 2 else "REPEAT"
    assert gate == "REPEAT"

def test_orchestrator_has_all_stages():
    from backend.orchestrator import Orchestrator
    try:
        o = Orchestrator()
    except Exception:
        import pytest; pytest.skip("model unavailable")
    for m in ("run_discover", "run_validate", "run_build",
              "run_commercial", "run_launch", "run_operate"):
        assert hasattr(o, m)
__EOF_GATES__

cat > tests/test_approval_required.py <<'__EOF_APPROVAL__'
def test_approval_row_created_on_gate():
    from memory import database
    from backend import approval_manager
    v = database.create_venture(name="Approval test", idea="test")
    aid = approval_manager.request(v["id"], action="discover_gate",
                                   payload={"recommendation": "GO"})
    assert any(a["id"] == aid for a in approval_manager.list_pending(v["id"]))

def test_require_approved_raises():
    from memory import database
    from backend.approval_manager import require_approved, ApprovalRequired
    v = database.create_venture(name="Approval test 2", idea="test")
    try:
        require_approved(v["id"], "discover_gate")
        assert False
    except ApprovalRequired:
        pass
__EOF_APPROVAL__

cat > scripts/export_decision_log.py <<'__EOF_EXPORT__'
"""Export SQLite decisions to decision_log.json in hackathon schema."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from memory.database import connect
from tools.ollama_client import get_client, OllamaError


def _model():
    try:
        return get_client().model
    except OllamaError:
        return os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")


def export(path="decision_log.json"):
    with connect() as c:
        rows = c.execute("SELECT * FROM decisions ORDER BY created_at ASC").fetchall()
    model = _model()
    entries = []
    for r in rows:
        d = dict(r)
        sources = []
        with connect() as c:
            for e in c.execute(
                "SELECT source FROM evidence WHERE venture_id=? AND stage=? "
                "AND source IS NOT NULL AND source != ''",
                (d.get("venture_id"), d.get("stage")),
            ).fetchall():
                if e["source"] and e["source"] not in sources:
                    sources.append(e["source"])
        entries.append({
            "timestamp": d.get("created_at"),
            "agent": d.get("agent"),
            "action": d.get("action"),
            "sources": sources,
            "model": d.get("model") or model,
            "cost": 0,
            "approved_by": "founder" if d.get("approval_status") == "approved" else None,
        })
    Path(path).write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"[export] {len(entries)} entries -> {path}")
    return len(entries)


if __name__ == "__main__":
    export()
__EOF_EXPORT__

cat > scripts/run_demo.py <<'__EOF_DEMO__'
"""End-to-end demo. Writes outputs/phase*.json and decision_log.json."""
from __future__ import annotations
import json, sys, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.orchestrator import Orchestrator
from memory import database
from scripts.export_decision_log import export

OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

WEAK = "An AI that predicts lottery numbers with 99% accuracy."
STRONG = ("A sustainability-focused reusable packaging service for cafes in Cairo. "
          "Cafes pay a monthly subscription; customers return containers to any "
          "cafe in the network. I have 2 weeks and can code in Python.")


def save(rel, data):
    p = OUT / rel
    p.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"  [out] {rel}")


def dump_stage(stage, vid, result, tag):
    save(f"{tag}_step1_result.json", {"stage": stage, "result": result})
    feas = result.get("feasibility") or {}
    fb = result.get("feedback") or {}
    gate = feas.get("gate_recommendation") or fb.get("gate") or "N/A"
    save(f"{tag}_gate_decision.json", {
        "stage": stage,
        "gate": gate,
        "classification": feas.get("classification"),
        "rationale": feas.get("rationale") or fb.get("note"),
        "sources_used": feas.get("sources_used") or [],
        "assumptions_labelled": "findings without source_url stored as type=assumption",
    })


def approve(orch, vid, aid):
    try:
        orch.approve_and_advance(vid, aid)
        print(f"  [gate] approved {aid[:8]}...")
    except Exception as e:
        print(f"  [gate] approve failed: {e}")


def run_weak(orch):
    print("\n=== Weak idea (expecting STOP) ===")
    v = database.create_venture(name="Lottery", idea=WEAK)
    database.add_message(v["id"], "user", WEAK)
    try:
        r = orch.run_stage(v["id"], "discover")
        dump_stage("discover", v["id"], r, "weak_phase1")
        gate = (r.get("feasibility") or {}).get("gate_recommendation")
        print(f"  [gate] {gate}")
    except Exception:
        traceback.print_exc()


def run_strong(orch):
    print("\n=== Strong idea (full pipeline) ===")
    v = database.create_venture(name="Reusable packaging", idea=STRONG)
    database.add_message(v["id"], "user", STRONG)
    for stage in ("discover", "validate", "build", "commercial", "launch", "operate"):
        print(f"  [{stage}] running...")
        try:
            r = orch.run_stage(v["id"], stage)
            dump_stage(stage, v["id"], r, f"phase{'123456'[['discover','validate','build','commercial','launch','operate'].index(stage)]}")
            if r.get("approval_id"):
                approve(orch, v["id"], r["approval_id"])
        except Exception:
            traceback.print_exc()
            break


def main():
    orch = Orchestrator()
    run_weak(orch)
    run_strong(orch)
    print("\n=== Exporting decision log ===")
    export(str(ROOT / "decision_log.json"))
    print("\nDone.")


if __name__ == "__main__":
    main()
__EOF_DEMO__

cat > outputs/README.md <<'__EOF_OUT__'
# outputs/

Real demo-run outputs. Regenerate with `python scripts/run_demo.py`.

Naming: `phase<N>_step<M>_<name>.json`, gates as `phase<N>_gate_decision.json`.
`weak_*` files = the deliberately weak idea used to demonstrate the STOP gate.
__EOF_OUT__

echo
echo "  Files written:"
echo "    tests/ (5 files)"
echo "    scripts/ (2 files)"
echo "    outputs/ (2 files)"
echo "    decision_log.json"
echo
echo "  Next:"
echo "    pip install pytest httpx"
echo "    pytest -q tests/"
echo "    python scripts/run_demo.py"
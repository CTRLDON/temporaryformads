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

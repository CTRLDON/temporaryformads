from __future__ import annotations
import json, uuid
from typing import Any
from memory.database import connect
from memory.schemas import utcnow

def current_model_name() -> str:
    try:
        from tools.ollama_client import get_client
        return getattr(get_client(), "model", "unknown") or "unknown"
    except Exception:
        return "unknown"

def log(vid, *, stage, agent, action, decision, rationale,
        model=None, evidence_ids=None, approval_status="not_required") -> str:
    did = str(uuid.uuid4())
    with connect() as c:
        c.execute(
            "INSERT INTO decisions (id,venture_id,stage,agent,action,decision,"
            "rationale,evidence_ids_json,approval_status,model,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (did, vid, stage, agent, action, decision, rationale,
             json.dumps(evidence_ids or []), approval_status,
             model or current_model_name(), utcnow()))
    return did

def list_for(vid, limit=200):
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM decisions WHERE venture_id=? "
            "ORDER BY created_at DESC LIMIT ?", (vid, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["evidence_ids"] = json.loads(d.pop("evidence_ids_json") or "[]")
        except Exception:
            d["evidence_ids"] = []
        out.append(d)
    return out

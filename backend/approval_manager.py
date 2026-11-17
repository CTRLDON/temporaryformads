from __future__ import annotations
import json, uuid
from typing import Any
from memory.database import connect
from memory.schemas import utcnow

class ApprovalRequired(Exception):
    pass

def request(vid, action, payload):
    aid = str(uuid.uuid4())
    with connect() as c:
        c.execute(
            "INSERT INTO approvals (id,venture_id,action,payload_json,status,created_at) "
            "VALUES (?,?,?,?,?,?)", (aid, vid, action, json.dumps(payload),
                                     "pending", utcnow()))
    return aid

def resolve(aid, status):
    if status not in ("approved", "rejected"):
        raise ValueError("bad status")
    with connect() as c:
        c.execute("UPDATE approvals SET status=?, resolved_at=? WHERE id=?",
                  (status, utcnow(), aid))

def list_pending(vid):
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM approvals WHERE venture_id=? AND status='pending' "
            "ORDER BY created_at DESC", (vid,)).fetchall()
    return [{**dict(r), "payload": json.loads(r["payload_json"])} for r in rows]

def require_approved(vid, action):
    with connect() as c:
        row = c.execute(
            "SELECT 1 FROM approvals WHERE venture_id=? AND action=? "
            "AND status='approved' LIMIT 1", (vid, action)).fetchone()
    if not row:
        raise ApprovalRequired(f"Action '{action}' requires approval")

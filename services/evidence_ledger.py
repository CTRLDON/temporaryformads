from __future__ import annotations
import uuid
from typing import Any
from memory.database import connect
from memory.schemas import utcnow

def add(vid, *, type, claim, source=None, details=None, agent=None, stage=None) -> str:
    eid = str(uuid.uuid4())
    with connect() as c:
        c.execute(
            "INSERT INTO evidence (id,venture_id,type,claim,source,details,agent,stage,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (eid, vid, type, claim, source, details, agent, stage, utcnow()))
    return eid

def list_for(vid, *, stage=None):
    sql = "SELECT * FROM evidence WHERE venture_id=?"; args = [vid]
    if stage:
        sql += " AND stage=?"; args.append(stage)
    sql += " ORDER BY created_at DESC"
    with connect() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]

def summary(vid):
    with connect() as c:
        rows = c.execute(
            "SELECT type, COUNT(*) n FROM evidence WHERE venture_id=? GROUP BY type",
            (vid,)).fetchall()
    return {r["type"]: r["n"] for r in rows}

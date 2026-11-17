from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

@dataclass
class Venture:
    id: str
    name: str
    idea: str
    theme: str = "indigo"
    current_stage: str = "discover"
    brief: dict = field(default_factory=dict)
    gate: str = "pending"
    gate_rationale: str = ""
    created_at: str = field(default_factory=utcnow)
    updated_at: str = field(default_factory=utcnow)
    def to_dict(self):
        return asdict(self)

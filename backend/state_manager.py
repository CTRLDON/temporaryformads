from __future__ import annotations
from memory import database

class StateManager:
    @staticmethod
    def get_venture(vid):
        return database.get_venture(vid)

    @staticmethod
    def set_stage(vid, stage, status):
        database.set_stage_status(vid, stage, status)

    @staticmethod
    def advance_stage(vid):
        from config import STAGES
        v = database.get_venture(vid)
        if not v:
            return None
        stages = database.get_stages(vid)
        current = v["current_stage"]
        if stages[current]["status"] != "completed":
            return current
        idx = STAGES.index(current) if current in STAGES else 0
        if idx + 1 >= len(STAGES):
            return current
        nxt = STAGES[idx + 1]
        database.update_venture(vid, current_stage=nxt)
        return nxt

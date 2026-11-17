from __future__ import annotations
from agents.base import BaseAgent
from services import evidence_ledger


class MarketingAgent(BaseAgent):
    name = "marketing"
    description = "Marketing copy with evidence-linked claims."
    system_prompt = ("You write honest marketing copy. Never invent "
                    "testimonials, customers, revenue, or guarantees.")

    def generate_launch_materials(self, venture, evidence):
        ev = [{"id": e["id"][:8], "type": e["type"], "claim": e["claim"],
               "source": e["source"]} for e in evidence[:20]]
        schema = (
            '{"tagline": "string", "one_liner": "string", '
            '"claims": [{"text": "string", "evidence_id": "string", '
            '"status": "supported|unsupported"}], "call_to_action": "string"}'
        )
        result = self._chat_json({
            "venture_idea": venture["idea"], "brief": venture.get("brief", {}),
            "evidence": ev,
            "instruction": "Cite evidence per claim OR mark unsupported.",
        }, schema_hint=schema)

        unsupported = []
        for c in result.get("claims", []):
            if c.get("status") == "unsupported" or not c.get("evidence_id"):
                c["status"] = "unsupported"
                unsupported.append(c.get("text", ""))
                evidence_ledger.add(venture["id"], type="assumption",
                                    claim=f"Marketing claim (UNSUPPORTED): {c.get('text','')}",
                                    agent=self.name, stage="launch")
            else:
                evidence_ledger.add(venture["id"], type="verified",
                                    claim=f"Marketing claim (verified): {c.get('text','')}",
                                    source=f"evidence:{c['evidence_id']}",
                                    agent=self.name, stage="launch")

        return {"tagline": result.get("tagline", ""),
                "one_liner": result.get("one_liner", ""),
                "claims": result.get("claims", []),
                "unsupported_claims": unsupported,
                "call_to_action": result.get("call_to_action", "")}

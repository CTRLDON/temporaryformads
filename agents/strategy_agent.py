from __future__ import annotations
from agents.base import BaseAgent
from services import evidence_ledger


class StrategyAgent(BaseAgent):
    name = "strategy"
    description = "Lean MVP specification from validated evidence."
    system_prompt = ("You produce small, specific MVP specs. Every feature "
                    "MUST trace to a customer need or evidence-backed assumption.")

    def generate_mvp_spec(self, venture, evidence):
        ev = [{"type": e["type"], "claim": e["claim"]} for e in evidence[:20]]
        schema = (
            '{"features": [{"name": "string", "purpose": "string", '
            '"traced_to": "string", "acceptance": "string"}], '
            '"out_of_scope": ["string"], '
            '"tech_stack": {"language": "string", "framework": "string", '
            '"database": "string", "rationale": "string"}}'
        )
        result = self._chat_json({
            "venture_idea": venture["idea"], "brief": venture.get("brief", {}),
            "evidence": ev,
            "instruction": "Design SMALLEST possible MVP — 3 to 5 features. Each must trace to evidence.",
        }, schema_hint=schema)
        for feat in result.get("features", []):
            evidence_ledger.add(venture["id"], type="assumption",
                                claim=f"Feature: {feat.get('name')} — {feat.get('purpose','')}",
                                details=f"Traced to: {feat.get('traced_to','')}",
                                agent=self.name, stage="build")
        return result

from __future__ import annotations
from agents.base import BaseAgent
from services import evidence_ledger


class CommercialAgent(BaseAgent):
    name = "commercial"
    description = "Proposes pricing grounded in evidence."
    system_prompt = "Propose pricing from evidence. If no evidence, say so and propose an experiment."

    def prepare_pricing(self, venture, evidence):
        ev = [{"type": e["type"], "claim": e["claim"]} for e in evidence[:20]]
        schema = (
            '{"model": "one-time|subscription|usage|freemium|marketplace", '
            '"price_per_unit": "string", "unit": "string", "rationale": "string", '
            '"competitor_anchors": ["string"], "confidence": "high|medium|low"}'
        )
        result = self._chat_json({
            "venture_idea": venture["idea"], "brief": venture.get("brief", {}),
            "evidence": ev,
            "instruction": "Propose pricing. If no pricing evidence, use confidence=low.",
        }, schema_hint=schema)

        evidence_ledger.add(venture["id"], type="assumption",
                            claim=f"Pricing: {result.get('model')} at {result.get('price_per_unit')} {result.get('unit','')}",
                            details=result.get("rationale", ""),
                            agent=self.name, stage="commercial")
        return result

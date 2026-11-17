from __future__ import annotations
from agents.base import BaseAgent
from services import evidence_ledger


class FeasibilityAgent(BaseAgent):
    name = "feasibility"
    description = "Rigorous feasibility verdict with per-dimension reasoning."
    system_prompt = (
        "You MUST decide. NEVER output UNDETERMINED. If evidence is thin, "
        "classify as CONDITIONALLY FEASIBLE or NOT FEASIBLE and explain which "
        "dimensions are weak. Classification: FEASIBLE, CONDITIONALLY FEASIBLE, "
        "or NOT FEASIBLE. Gate: GO, REPEAT, PIVOT, or STOP."
    )

    def run(self, context):
        venture = context["venture"]
        stage = context.get("stage", "discover")
        evidence = evidence_ledger.list_for(venture["id"])
        evidence_pack = [{"id": e["id"][:8], "type": e["type"],
                          "claim": e["claim"], "source": e["source"]}
                         for e in evidence[:40]]

        schema = (
            '{"classification": "FEASIBLE|CONDITIONALLY FEASIBLE|NOT FEASIBLE", '
            '"dimensions": {"market": {"score": "strong|ok|weak", "reason": "string"}, '
            '"financial": {"score": "string", "reason": "string"}, '
            '"technical": {"score": "string", "reason": "string"}, '
            '"operational": {"score": "string", "reason": "string"}, '
            '"competitive": {"score": "string", "reason": "string"}}, '
            '"risks": ["string"], "unresolved_assumptions": ["string"], '
            '"gate_recommendation": "GO|REPEAT|PIVOT|STOP", '
            '"rationale": "string (3-5 sentences, plain English)", '
            '"sources_used": ["string (URLs)"], '
            '"next_steps": ["string (concrete actions)"]}'
        )
        result = self._chat_json({
            "venture_idea": venture["idea"], "brief": venture.get("brief", {}),
            "evidence_count": len(evidence), "evidence": evidence_pack,
            "instruction": "Assess feasibility using ONLY the provided evidence. Return a decision.",
        }, schema_hint=schema)

        self._record(venture["id"], type="assumption",
                     claim=f"Feasibility: {result.get('classification')} (gate: {result.get('gate_recommendation')})",
                     stage=stage, details=result.get("rationale", ""))
        return result

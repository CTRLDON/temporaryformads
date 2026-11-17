from __future__ import annotations
from agents.base import BaseAgent
from services import evidence_ledger


class OperationsAgent(BaseAgent):
    name = "operations"
    description = "Analyzes metrics and produces recommendations."
    system_prompt = ("Analyze metrics. Refuse generic advice. Every "
                    "recommendation must tie to a metric observation.")

    def analyze(self, venture, metrics):
        schema = (
            '{"issues": [{"observation": "string", "severity": "high|medium|low"}], '
            '"recommendations": [{"action": "string", "rationale": "string", '
            '"expected_impact": "string"}], "missing_metrics": ["string"]}'
        )
        result = self._chat_json({
            "venture_idea": venture["idea"], "metrics": metrics,
            "instruction": "Analyze metrics. Concrete recommendations only.",
        }, schema_hint=schema)

        for issue in result.get("issues", []):
            evidence_ledger.add(venture["id"], type="assumption",
                                claim=f"Operational issue: {issue.get('observation','')}",
                                agent=self.name, stage="operate")
        for rec in result.get("recommendations", []):
            evidence_ledger.add(venture["id"], type="assumption",
                                claim=f"Recommendation: {rec.get('action','')}",
                                details=rec.get("rationale", ""),
                                agent=self.name, stage="operate")
        return result

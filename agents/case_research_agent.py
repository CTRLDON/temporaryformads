from __future__ import annotations
from agents.base import BaseAgent
from services import evidence_ledger
from tools import web_search


class CaseResearchAgent(BaseAgent):
    name = "case_research"
    description = "Finds comparable historical business cases."
    system_prompt = ("Summarize real, documented cases. Cite source URL. "
                    "Never invent company names or outcomes.")

    def find_similar_cases(self, venture, problem):
        raw = web_search.search(f"startup case study {problem} pivot outcome", 5)
        sources = raw.get("results", [])
        if not sources:
            return {"cases": [], "error": raw.get("error", "no results")}
        schema = (
            '{"cases": [{"company": "string", "situation": "string", '
            '"strategy": "string", "outcome": "string", '
            '"source_url": "string", "applicability": "string"}]}'
        )
        result = self._chat_json({
            "problem": problem, "venture_brief": venture.get("brief", {}),
            "search_results": sources,
            "instruction": "Extract up to 3 real cases with source URLs.",
        }, schema_hint=schema)

        for case in result.get("cases", []):
            evidence_ledger.add(venture["id"],
                                type="verified" if case.get("source_url") else "assumption",
                                claim=f"Historical case: {case.get('company','?')} — {case.get('outcome','')}",
                                source=case.get("source_url"),
                                details=case.get("situation", ""),
                                agent=self.name, stage="operate")
        return result

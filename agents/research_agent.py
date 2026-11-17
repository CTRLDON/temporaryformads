from __future__ import annotations
from typing import Any
from agents.base import BaseAgent
from tools import web_search


class ResearchAgent(BaseAgent):
    name = "research"
    description = "Targeted market/competitor research with sources."
    system_prompt = ("You are a careful market-research analyst. Use ONLY the "
                    "provided search results. Cite source URL for every claim.")

    def run(self, context):
        venture = context["venture"]
        stage = context.get("stage", "discover")
        question = context.get("question",
                               f"Market landscape for: {venture['idea'][:200]}")
        raw = web_search.search(question, max_results=6)
        sources = raw["results"]; error = raw.get("error")
        query_used = raw.get("query_used", question)

        schema = ('{"findings": [{"claim": "string", "source_url": "string", '
                  '"confidence": "high|medium|low"}], "limitations": ["string"]}')

        if not sources:
            self._record(venture["id"], type="assumption",
                         claim=f"No search results for: {question}",
                         stage=stage, details=error or "no results")
            return {"findings": [], "limitations": [error or "no sources"],
                    "sources": [], "query_used": query_used}

        result = self._chat_json({
            "question": question, "search_results": sources,
            "instruction": "Extract up to 5 findings with source_url. Every finding must cite one URL.",
        }, schema_hint=schema)

        findings = result.get("findings", [])
        for f in findings:
            self._record(venture["id"],
                         type="verified" if f.get("source_url") else "assumption",
                         claim=str(f.get("claim", "")), source=f.get("source_url"),
                         stage=stage, details=f"confidence={f.get('confidence','low')}")
        return {"findings": findings, "limitations": result.get("limitations", []),
                "sources": sources, "query_used": query_used}

"""BaseAgent — the contract every agent follows.

Note: `run()` is INTENTIONALLY not abstract. Many agents expose a more
meaningful named method instead (e.g. StrategyAgent.generate_mvp_spec,
FinancialAgent.model_unit_economics). Requiring every agent to also
implement a generic run() would be ceremony with no value. Agents that
DO have a natural single-entry workflow (Research, Feasibility, Founder)
override run() themselves.
"""
from __future__ import annotations
import json
from typing import Any

from services import evidence_ledger
from tools.ollama_client import OllamaClient, OllamaError, get_client


class AgentError(RuntimeError):
    pass


class BaseAgent:
    name: str = "base"
    description: str = ""
    system_prompt: str = "You are a helpful business reasoning agent."

    def __init__(self, client: OllamaClient | None = None):
        self.client = client or get_client()

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Optional default entry point.

        Agents with a specialized method (generate_mvp_spec, etc.) do NOT
        need to override this — the orchestrator calls the specific method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement run(). "
            "Call its specific action method instead."
        )

    def _chat_json(self, payload, *, schema_hint=None):
        try:
            return self.client.chat_json(
                messages=[{
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, indent=2),
                }],
                system=self.system_prompt,
                schema_hint=schema_hint,
            )
        except OllamaError as e:
            raise AgentError(f"[{self.name}] {e}") from e

    def _record(self, vid, *, type, claim, source=None, stage=None, details=None):
        return evidence_ledger.add(
            vid, type=type, claim=claim, source=source,
            details=details, agent=self.name, stage=stage,
        )

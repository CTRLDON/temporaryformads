from __future__ import annotations
import re
from agents.base import BaseAgent
from services import evidence_ledger


def _parse_money(s):
    if not s: return None
    m = re.search(r"([\d.,]+)\s*([km]?)\s*([A-Z]{2,3}|[€$£])?", str(s), re.IGNORECASE)
    if not m: return None
    try:
        num = float(m.group(1).replace(",", ""))
        if m.group(2).lower() == "k": num *= 1000
        elif m.group(2).lower() == "m": num *= 1000000
        return num
    except ValueError:
        return None


class FinancialAgent(BaseAgent):
    name = "financial"
    description = "Unit economics with transparent formulas."
    system_prompt = "Conservative financial modeling with explicit formulas."

    def model_unit_economics(self, venture, pricing):
        brief = venture.get("brief", {})
        schema = (
            '{"price_per_unit": "number", "variable_cost_per_unit": "number", '
            '"fixed_costs_monthly": "number", "rationale": "string", '
            '"assumptions_used": ["string"], "currency": "string"}'
        )
        result = self._chat_json({
            "venture_idea": venture["idea"], "brief": brief, "pricing": pricing,
            "instruction": "Estimate price, variable cost, fixed costs. Numeric only. Be conservative.",
        }, schema_hint=schema)

        try:
            price = float(result.get("price_per_unit", 0))
            vc = float(result.get("variable_cost_per_unit", 0))
            fc = float(result.get("fixed_costs_monthly", 0))
        except (TypeError, ValueError):
            price, vc, fc = 0.0, 0.0, 0.0

        cm = price - vc
        gm = (cm / price * 100) if price > 0 else 0.0
        be = (fc / cm) if cm > 0 else None

        for label, value in [("price per unit", price), ("variable cost", vc),
                             ("fixed costs", fc),
                             ("contribution margin", round(cm, 2)),
                             ("gross margin %", round(gm, 1)),
                             ("break-even units", round(be) if be else "N/A")]:
            evidence_ledger.add(venture["id"], type="assumption",
                                claim=f"Unit economics · {label}: {value}",
                                agent=self.name, stage="commercial")

        return {
            "price_per_unit": price, "variable_cost_per_unit": vc,
            "fixed_costs_monthly": fc, "contribution_margin": round(cm, 2),
            "gross_margin_pct": round(gm, 1),
            "break_even_units": round(be) if be else None,
            "assumptions": result.get("assumptions_used", []),
            "rationale": result.get("rationale", ""),
            "currency": result.get("currency", ""),
            "formulas": {"contribution_margin": "price - vc",
                         "gross_margin_pct": "(price - vc) / price * 100",
                         "break_even_units": "fixed_costs / contribution_margin"},
        }

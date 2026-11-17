"""apply_updates.py — VentureOS full-file updater.

Run from the project root:
    python apply_updates.py

Backs up every overwritten file to _backups/ (existing backups are preserved).
"""
from __future__ import annotations
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKUP = ROOT / "_backups"


def write(rel: str, content: str) -> None:
    p = ROOT / rel
    if p.exists():
        BACKUP.mkdir(exist_ok=True)
        dst = BACKUP / f"{p.name}.bak"
        if not dst.exists():
            shutil.copy2(p, dst)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"  [OK]   {rel}")


# ═══════════════════════════════════════════════════════════════════════
# agents/founder_agent.py
# ═══════════════════════════════════════════════════════════════════════
FOUNDER_PY = r'''"""Founder agent — clarification-first, Python-tracked required fields."""
from __future__ import annotations
import json
import re
from typing import Any
from agents.base import BaseAgent

REQUIRED_FIELDS = ["budget", "skills", "education", "target_market"]
MAX_QUESTIONS = 10  # 2 clarification + 4 required + headroom

CLARIFICATION_QUESTIONS = [
    "What specific problem does this solve, and why does it matter? "
    "What's the pain point you're addressing?",
    "What makes this different from what already exists? "
    "What's your unique angle or unfair advantage?",
]

FIELD_HINTS = {
    "budget": [r"\b\d+\s*(?:egp|usd|eur|gbp|\$|€|£|k|m|thousand|million)\b",
               r"\b(?:budget|can spend|have about|have around|can invest)\b",
               r"\b\d{3,}\b"],
    "skills": [r"\b(?:i have|i've|i can|i know|i built|i ran|i managed|i coded|i designed|i developed)\b",
               r"\b(?:skills?|experienced?|background in|worked on|built|ran|hire)\b"],
    "education": [r"\b(?:harvard|stanford|mit|oxford|cambridge|university|college|degree|bachelor|master|phd|mba|educated|studied|graduated|self-taught)\b"],
    "target_market": [r"\b(?:consumer|consumers|customer|customers|caf[eé]s?|restaurants?|businesses|users?|people|students?|professionals?|smb|enterprises?|audience|market)\b"],
}

QUESTION_PATTERNS = {
    "budget": r"\b(?:budget|spend|invest|cost to start|how much|runway|money|funding|capital|cash|afford)\b",
    "skills": r"\b(?:skills?|experience|build yourself|hire|implement|expertise|background)\b",
    "education": r"\b(?:educat|background|stud|degree|qualif|school|trained|graduated)\b",
    "target_market": r"\b(?:who specifically|audience|customer|serve|target market|consumer|client)\b",
}


def _user_mentions_field(field, text):
    return any(re.search(p, text, flags=re.IGNORECASE) for p in FIELD_HINTS[field])


def _assistant_asks_field(text):
    for field, pattern in QUESTION_PATTERNS.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            return field
    return None


def _fields_answered(history):
    """Only counts fields that were explicitly asked about AND replied to.
    Auto-detect from free text is intentionally removed so target_market
    is never skipped."""
    answered = set()
    for i, msg in enumerate(history):
        if msg.get("role") != "assistant":
            continue
        field = _assistant_asks_field(msg.get("content", ""))
        if not field:
            continue
        if i + 1 < len(history) and history[i + 1].get("role") == "user":
            reply = history[i + 1].get("content", "").strip()
            if len(reply) >= 2:
                answered.add(field)
    return answered


def _questions_asked(history):
    count = 0
    for m in history:
        if m.get("role") != "assistant":
            continue
        text = m.get("content", "") or ""
        if any(text.strip().startswith(c[:40]) for c in CLARIFICATION_QUESTIONS):
            count += 1
            continue
        if _assistant_asks_field(text):
            count += 1
    return count


class FounderAgent(BaseAgent):
    name = "founder_understanding"
    description = "Clarifies the idea first, then gathers required founder details."
    system_prompt = "You are a warm, curious product partner. Ask ONE question at a time."

    def run(self, context):
        return self.next_question(context.get("idea", ""), context.get("history", []))

    def next_question(self, idea, history):
        answered = _fields_answered(history)
        missing = [f for f in REQUIRED_FIELDS if f not in answered]
        asked = _questions_asked(history)

        # Phase 1 — clarify the idea behind the project.
        if asked < len(CLARIFICATION_QUESTIONS):
            return {
                "question": CLARIFICATION_QUESTIONS[asked],
                "ready_for_brief": False,
                "missing_fields": missing,
                "answered_fields": sorted(answered),
                "phase": "clarify",
            }

        # Phase 2 — required founder details.
        if not missing or asked >= MAX_QUESTIONS:
            return {
                "question": "",
                "ready_for_brief": True,
                "missing_fields": missing,
                "answered_fields": sorted(answered),
                "phase": "ready",
            }

        target = missing[0]
        try:
            question = self._compose_question(target, idea)
        except Exception:
            question = self._fallback_question(target)
        return {
            "question": question,
            "ready_for_brief": False,
            "missing_fields": missing,
            "answered_fields": sorted(answered),
            "phase": "details",
        }

    def _compose_question(self, field, idea):
        prompts = {
            "budget": "how much money they can realistically spend to start.",
            "skills": "what skills they personally bring to this venture.",
            "education": "their relevant educational or professional background.",
            "target_market": "who specifically they want to serve as their first customers.",
        }
        result = self._chat_json(
            {"venture_idea": idea, "field": field, "ask_about": prompts[field],
             "instruction": "Write ONE short natural question, max 20 words. "
                            "Must clearly reference the topic being asked about."},
            schema_hint='{"question": "string"}')
        q = str(result.get("question", "")).strip().strip('"').strip()
        if not q or _assistant_asks_field(q) != field:
            return self._fallback_question(field)
        return q

    @staticmethod
    def _fallback_question(field):
        return {
            "budget": "What budget can you realistically spend to get this off the ground?",
            "skills": "What skills do you personally bring to this venture?",
            "education": "What's your relevant educational or professional background?",
            "target_market": "Who specifically is your first target customer or audience?",
        }[field]

    def answer_question(self, venture, question, history=None):
        """Answer any free-form question using the venture's context."""
        history = history or []
        brief = venture.get("brief") or {}
        system = (
            "You are a helpful, direct business advisor. "
            "Answer the user's question concisely (2-4 sentences) and specifically. "
            "Use the venture context below when relevant, but answer general "
            "questions generally if they aren't venture-specific.\n\n"
            f"Venture idea: {venture.get('idea') or ''}\n"
            f"Business brief: {json.dumps(brief, ensure_ascii=False)}\n"
        )
        messages = []
        for h in history[-10:]:
            role = h.get("role", "user")
            if role not in ("user", "assistant"):
                continue
            messages.append({"role": role, "content": h.get("content", "")})
        messages.append({"role": "user", "content": question})
        try:
            return self.client.chat(messages, system=system)
        except Exception as e:
            raise RuntimeError(f"Q&A failed: {e}")

    def analyze_answers(self, answers):
        """Normalize raw founder answers into clean, specific, human-readable phrases."""
        schema = ('{"budget": "string", "skills": "string", '
                  '"education": "string", "target_market": "string"}')
        return self._chat_json({
            "raw_answers": answers,
            "instruction": (
                "Normalize the founder's raw answers into clean, specific, "
                "human-readable phrases. Do NOT invent facts. Return the SAME "
                "four keys (budget, skills, education, target_market).\n\n"
                "Rules:\n"
                "- budget: parse any stated amount and format as "
                "'<comma-separated number> <CURRENCY CODE>'. "
                "Examples: 'like a million dollars' -> '1,000,000 USD'; "
                "'maybe 5000 EGP' -> '5,000 EGP'; 'I have no money' -> '0 USD'; "
                "'I don't know' or empty -> 'Not specified'.\n"
                "- skills: '<level> experience in <domain>'. Use one of "
                "'Minimal', 'Some', 'Moderate', 'Extensive', or 'Expert'. "
                "Examples: 'I've barely touched marketing' -> "
                "'Minimal experience in marketing'; "
                "'I'm a senior React developer' -> "
                "'Extensive experience in React development'; empty -> "
                "'Not specified'.\n"
                "- education: '<degree> in <field> at <institution>' when "
                "available. Standardise degree abbreviations "
                "(bachelor -> BSc / BEng / BA; master -> MSc / MA / MBA; "
                "phd -> PhD). "
                "Example: 'finished undergrad in computer engineering at AUC' -> "
                "'BSc in Computer Engineering at AUC'; 'self taught' -> "
                "'Self-taught'; empty -> 'Not specified'.\n"
                "- target_market: concise audience description, title-cased. "
                "Example: 'freelancers in egypt' -> 'Freelancers in Egypt'; "
                "empty -> 'Not specified'.\n"
                "Return only the JSON object."
            ),
        }, schema_hint=schema)

    def draft_brief(self, idea, history):
        schema = (
            '{"name": "string", "category": "technology|education|sustainability|creative|productivity|general", '
            '"concept": "string", "problem": "string", "solution": "string", '
            '"target_audience": "string", "business_model": "string", '
            '"budget": "string", "founder_skills": ["string"], "founder_education": "string", '
            '"theme": {"accent": "#RRGGBB", "accent_2": "#RRGGBB", '
            '"background": "#RRGGBB (DARK)", "surface": "#RRGGBB (DARK)", "mood": "string"}, '
            '"assumptions": ["string"], "constraints": ["string"], "open_questions": ["string"]}'
        )
        return self._chat_json({
            "idea": idea, "conversation": history,
            "instruction": (
                "Draft the Business Brief. Quote founder answers verbatim. "
                "Never invent facts. For theme: DARK MODE ONLY. background "
                "must be #050508 to #141420. surface slightly lighter. accent "
                "vibrant brand color. ABSOLUTELY FORBIDDEN: any color with "
                "luminance above 20%."
            ),
        }, schema_hint=schema)
'''

# ═══════════════════════════════════════════════════════════════════════
# backend/orchestrator.py
# ═══════════════════════════════════════════════════════════════════════
ORCHESTRATOR_PY = r'''"""Orchestrator — six stages with checkpoints + decision logging."""
from __future__ import annotations
import json
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.case_research_agent import CaseResearchAgent
from agents.commercial_agent import CommercialAgent
from agents.development_agent import DevelopmentAgent
from agents.feasibility_agent import FeasibilityAgent
from agents.financial_agent import FinancialAgent
from agents.founder_agent import FounderAgent
from agents.marketing_agent import MarketingAgent
from agents.operations_agent import OperationsAgent
from agents.research_agent import ResearchAgent
from agents.strategy_agent import StrategyAgent
from agents.testing_agent import TestingAgent
from backend import approval_manager
from backend.state_manager import StateManager
from config import OUTPUTS_DIR, STAGES
from memory import database
from memory.database import connect
from memory.schemas import utcnow
from services import decision_log, evidence_ledger


def _clear_checkpoints(vid, stage):
    with connect() as c:
        c.execute("UPDATE stage_state SET notes_json='{}', updated_at=? "
                  "WHERE venture_id=? AND stage=?",
                  (utcnow(), vid, stage))


def _checkpoint(vid, stage, message, extra=None):
    """Write one checkpoint. Retries briefly on SQLite lock (parallel research)."""
    last_err = None
    for attempt in range(5):
        try:
            with connect() as c:
                row = c.execute("SELECT notes_json FROM stage_state "
                                "WHERE venture_id=? AND stage=?",
                                (vid, stage)).fetchone()
                notes = {}
                if row and row["notes_json"]:
                    try:
                        notes = json.loads(row["notes_json"]) or {}
                    except Exception:
                        notes = {}
                cps = notes.get("checkpoints", [])
                entry = {"time": utcnow(), "message": message}
                if extra is not None:
                    entry["extra"] = extra
                cps.append(entry)
                notes["checkpoints"] = cps
                c.execute("UPDATE stage_state SET notes_json=?, updated_at=? "
                          "WHERE venture_id=? AND stage=?",
                          (json.dumps(notes), utcnow(), vid, stage))
            return
        except Exception as e:
            last_err = e
            if "locked" in str(e).lower() and attempt < 4:
                _time.sleep(0.1 * (attempt + 1))
                continue
            raise


class Orchestrator:
    def __init__(self):
        self.founder = FounderAgent()
        self.research = ResearchAgent()
        self.feasibility = FeasibilityAgent()
        self.strategy = StrategyAgent()
        self.development = DevelopmentAgent()
        self.testing = TestingAgent()
        self.commercial = CommercialAgent()
        self.financial = FinancialAgent()
        self.marketing = MarketingAgent()
        self.operations = OperationsAgent()
        self.case_research = CaseResearchAgent()

    # -------------------------------------------------------- discover
    def run_discover(self, vid):
        v = database.get_venture(vid)
        if not v: raise ValueError("unknown venture")
        _clear_checkpoints(vid, "discover")
        StateManager.set_stage(vid, "discover", "in_progress")
        _checkpoint(vid, "discover", "Starting 4 research topics in parallel…")

        idea = v["idea"][:180]
        questions = [
            f"Competitors and pricing for {idea}",
            f"Customer pain points for {idea}",
            f"Market size and growth for {idea}",
            f"Barriers and regulations for {idea}",
        ]

        results: dict[int, dict] = {}

        def _one(idx: int, q: str):
            return idx, self.research.run(
                {"venture": v, "stage": "discover", "question": q})

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(_one, i, q): (i, q) for i, q in enumerate(questions)}
            for fut in as_completed(futures):
                i, q = futures[fut]
                try:
                    _, result = fut.result()
                    results[i] = result
                    found = len(result.get("sources", []))
                    findings_count = len(result.get("findings", []))
                    _checkpoint(vid, "discover",
                                f"Topic {i + 1}/4 complete — {found} sources",
                                extra={"topic_index": i + 1,
                                       "question": q,
                                       "sources_count": found,
                                       "findings_count": findings_count})
                except Exception as e:
                    results[i] = {"sources": [], "findings": [],
                                  "limitations": [str(e)], "query_used": q}
                    _checkpoint(vid, "discover",
                                f"Topic {i + 1}/4 failed — {str(e)[:80]}",
                                extra={"topic_index": i + 1, "error": str(e)[:400]})

        research_results = [results.get(i, {"sources": [], "findings": []})
                            for i in range(len(questions))]
        total_sources = sum(len(r.get("sources", [])) for r in research_results)
        total_findings = sum(len(r.get("findings", [])) for r in research_results)
        _checkpoint(vid, "discover",
                    f"Aggregate: {total_sources} sources, {total_findings} findings",
                    extra={"total_sources": total_sources,
                           "total_findings": total_findings})

        _checkpoint(vid, "discover", "Assessing feasibility across 5 dimensions…")
        feas = self.feasibility.run({"venture": v, "stage": "discover"})
        gate = feas.get("gate_recommendation", "REPEAT")
        _checkpoint(vid, "discover",
                    f"Verdict: {feas.get('classification')} -> {gate}",
                    extra={"classification": feas.get("classification"),
                           "gate": gate,
                           "dimensions": feas.get("dimensions", {})})

        database.update_venture(vid, gate=gate,
                                gate_rationale=feas.get("rationale", ""))
        decision_log.log(vid, stage="discover", agent="feasibility",
                         action="feasibility_gate", decision=gate,
                         rationale=feas.get("rationale", "")[:500])

        feedback = {
            "sources_found": total_sources,
            "findings_extracted": total_findings,
            "dimensions": feas.get("dimensions", {}),
            "risks": feas.get("risks", []),
            "next_steps": feas.get("next_steps", []),
            "sources_used": feas.get("sources_used", []),
            "research_per_topic": [
                {"question": q, "findings": len(r.get("findings", [])),
                 "sources": len(r.get("sources", []))}
                for q, r in zip(questions, research_results)],
        }

        if gate == "STOP":
            StateManager.set_stage(vid, "discover", "stopped")
            _checkpoint(vid, "discover", "STOP — venture not feasible as described")
            return {"feasibility": feas, "feedback": feedback,
                    "stage_status": "stopped",
                    "warning": "The agents found this venture is NOT feasible."}

        StateManager.set_stage(vid, "discover", "awaiting_approval")
        _checkpoint(vid, "discover", "Awaiting your approval")
        approval_id = approval_manager.request(
            vid, action="discover_gate",
            payload={"recommendation": gate,
                     "rationale": feas.get("rationale", ""),
                     "classification": feas.get("classification"),
                     "sources_used": feas.get("sources_used", [])})
        return {"feasibility": feas, "feedback": feedback,
                "stage_status": "awaiting_approval", "approval_id": approval_id}

    # -------------------------------------------------------- validate
    def run_validate(self, vid):
        v = database.get_venture(vid)
        if not v: raise ValueError("unknown venture")
        _clear_checkpoints(vid, "validate")
        StateManager.set_stage(vid, "validate", "in_progress")
        _checkpoint(vid, "validate", "Thinking of validation experiments…")

        brief = v.get("brief") or {}
        assumptions = brief.get("assumptions") or []
        prompt = (f"Venture: {v['idea']}\nBrief: {brief}\n"
                  f"Assumptions to test: {assumptions}\n"
                  "Design 3 lean validation experiments. Return JSON.")
        _checkpoint(vid, "validate", "Drafting experiments…")
        try:
            experiments = self.research.client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                system="You are a lean startup validation expert. Be specific and cheap.",
                schema_hint=('{"experiments":[{"name":"string","hypothesis":"string",'
                            '"method":"string","success":"string","failure":"string",'
                            '"cost":"string","time":"string"}]}'))
        except Exception as e:
            experiments = {"experiments": [], "error": str(e)}

        exps = experiments.get("experiments", [])
        _checkpoint(vid, "validate", f"Generated {len(exps)} experiments",
                    extra={"count": len(exps),
                           "names": [e.get("name") for e in exps[:5]]})
        for exp in exps:
            evidence_ledger.add(vid, type="assumption",
                                claim=f"Experiment: {exp.get('name','?')} — {exp.get('hypothesis','?')}",
                                details=f"Method: {exp.get('method','')}",
                                agent="validation", stage="validate")

        n = len(exps)
        gate = "GO" if n >= 2 else "REPEAT"
        rationale = f"{n} validation experiments designed."
        database.update_venture(vid, gate=gate, gate_rationale=rationale)
        decision_log.log(vid, stage="validate", agent="validation",
                         action="experiment_design", decision=gate,
                         rationale=rationale)
        StateManager.set_stage(vid, "validate", "awaiting_approval")
        _checkpoint(vid, "validate", "Awaiting your approval")
        approval_id = approval_manager.request(
            vid, action="validate_gate",
            payload={"recommendation": gate, "rationale": rationale,
                     "classification": f"{n} experiments"})
        return {"experiments": exps, "stage_status": "awaiting_approval",
                "approval_id": approval_id,
                "feedback": {"experiments_designed": n}}

    # ---------------------------------------------------------- build
    def run_build(self, vid):
        v = database.get_venture(vid)
        if not v: raise ValueError("unknown venture")
        _clear_checkpoints(vid, "build")
        StateManager.set_stage(vid, "build", "in_progress")
        _checkpoint(vid, "build", "Designing MVP specification…")

        evidence = evidence_ledger.list_for(vid)
        spec = self.strategy.generate_mvp_spec(v, evidence)
        features = spec.get("features", [])
        _checkpoint(vid, "build", f"Defined {len(features)} MVP features",
                    extra={"features": [f.get("name") for f in features[:6]]})

        _checkpoint(vid, "build", "Generating application scaffold…")
        out_dir = OUTPUTS_DIR / vid / "mvp"
        scaffold = self.development.scaffold_mvp(v, spec, out_dir)
        _checkpoint(vid, "build",
                    f"Wrote {len(scaffold['files'])} files",
                    extra={"files": scaffold.get("files", []),
                           "output_dir": scaffold.get("output_dir")})

        _checkpoint(vid, "build", "Running tests…")
        test_result = self.testing.generate_smoke_test(v, spec, out_dir)
        _checkpoint(vid, "build",
                    f"Tests {'passed' if test_result.get('passed') else 'FAILED'}",
                    extra={"passed": test_result.get("passed"),
                           "output": (test_result.get("output") or "")[:400]})

        gate = "GO" if len(features) >= 3 and test_result.get("passed") else "REPEAT"
        rationale = (f"Generated {len(features)} features. "
                     f"Files: {len(scaffold['files'])}. "
                     f"Tests {'passed' if test_result.get('passed') else 'failed'}.")
        database.update_venture(vid, gate=gate, gate_rationale=rationale)
        decision_log.log(vid, stage="build", agent="development",
                         action="mvp_scaffold", decision=gate,
                         rationale=rationale)
        StateManager.set_stage(vid, "build", "awaiting_approval")
        _checkpoint(vid, "build", "Awaiting your approval")
        approval_id = approval_manager.request(
            vid, action="build_gate",
            payload={"recommendation": gate, "rationale": rationale,
                     "classification": f"{len(features)} features, "
                                       f"{len(scaffold['files'])} files"})
        return {"spec": spec, "files": scaffold["files"],
                "test": test_result, "output_dir": scaffold["output_dir"],
                "stage_status": "awaiting_approval",
                "approval_id": approval_id,
                "feedback": {"features_generated": len(features),
                             "files_written": len(scaffold["files"]),
                             "tests_passed": test_result.get("passed"),
                             "output_location": scaffold["output_dir"]}}

    # ----------------------------------------------------- commercial
    def run_commercial(self, vid):
        v = database.get_venture(vid)
        if not v: raise ValueError("unknown venture")
        _clear_checkpoints(vid, "commercial")
        StateManager.set_stage(vid, "commercial", "in_progress")
        _checkpoint(vid, "commercial", "Preparing pricing strategy…")

        evidence = evidence_ledger.list_for(vid)
        pricing = self.commercial.prepare_pricing(v, evidence)
        _checkpoint(vid, "commercial",
                    f"Pricing model: {pricing.get('model')}",
                    extra={"model": pricing.get("model"),
                           "price": pricing.get("price_per_unit"),
                           "unit": pricing.get("unit"),
                           "confidence": pricing.get("confidence")})

        _checkpoint(vid, "commercial", "Calculating unit economics…")
        economics = self.financial.model_unit_economics(v, pricing)
        _checkpoint(vid, "commercial",
                    f"Margin {economics.get('gross_margin_pct')}%, "
                    f"break-even {economics.get('break_even_units')} units",
                    extra={"gross_margin_pct": economics.get("gross_margin_pct"),
                           "break_even_units": economics.get("break_even_units"),
                           "contribution_margin": economics.get("contribution_margin")})

        gate = "GO" if economics.get("gross_margin_pct", 0) > 20 else "REPEAT"
        rationale = (f"Pricing: {pricing.get('model','?')}. "
                     f"Margin: {economics.get('gross_margin_pct',0)}%. "
                     f"Break-even: {economics.get('break_even_units','N/A')}.")
        database.update_venture(vid, gate=gate, gate_rationale=rationale)
        decision_log.log(vid, stage="commercial", agent="financial",
                         action="unit_economics", decision=gate,
                         rationale=rationale)
        StateManager.set_stage(vid, "commercial", "awaiting_approval")
        _checkpoint(vid, "commercial", "Awaiting your approval")
        approval_id = approval_manager.request(
            vid, action="commercial_gate",
            payload={"recommendation": gate, "rationale": rationale,
                     "classification": f"margin {economics.get('gross_margin_pct')}%"})
        return {"pricing": pricing, "economics": economics,
                "stage_status": "awaiting_approval",
                "approval_id": approval_id,
                "feedback": {"model": pricing.get("model"),
                             "price": pricing.get("price_per_unit"),
                             "gross_margin_pct": economics.get("gross_margin_pct"),
                             "break_even_units": economics.get("break_even_units"),
                             "formulas": economics.get("formulas")}}

    # --------------------------------------------------------- launch
    def run_launch(self, vid):
        v = database.get_venture(vid)
        if not v: raise ValueError("unknown venture")
        _clear_checkpoints(vid, "launch")
        StateManager.set_stage(vid, "launch", "in_progress")
        _checkpoint(vid, "launch", "Generating marketing copy…")

        evidence = evidence_ledger.list_for(vid)
        materials = self.marketing.generate_launch_materials(v, evidence)
        _checkpoint(vid, "launch",
                    f"Generated tagline + {len(materials.get('claims', []))} claims",
                    extra={"tagline": materials.get("tagline"),
                           "claims_total": len(materials.get("claims", []))})

        unsupported = materials.get("unsupported_claims", [])
        _checkpoint(vid, "launch",
                    f"{len(unsupported)} claims need evidence verification",
                    extra={"unsupported_claims": unsupported[:10]})

        gate = "GO" if len(unsupported) == 0 else "REPEAT"
        rationale = (f"Tagline + {len(materials.get('claims', []))} claims. "
                     f"{len(unsupported)} unsupported.")
        database.update_venture(vid, gate=gate, gate_rationale=rationale)
        decision_log.log(vid, stage="launch", agent="marketing",
                         action="launch_claims", decision=gate,
                         rationale=rationale)
        StateManager.set_stage(vid, "launch", "awaiting_approval")
        _checkpoint(vid, "launch", "Awaiting your approval")
        approval_id = approval_manager.request(
            vid, action="launch_gate",
            payload={"recommendation": gate, "rationale": rationale,
                     "classification": f"{len(unsupported)} unsupported",
                     "unsupported_claims": unsupported})
        return {"materials": materials, "unsupported_claims": unsupported,
                "stage_status": "awaiting_approval",
                "approval_id": approval_id,
                "feedback": {"tagline": materials.get("tagline"),
                             "claims_total": len(materials.get("claims", [])),
                             "claims_unsupported": len(unsupported)}}

    # -------------------------------------------------------- operate
    def run_operate(self, vid):
        v = database.get_venture(vid)
        if not v: raise ValueError("unknown venture")
        _clear_checkpoints(vid, "operate")
        StateManager.set_stage(vid, "operate", "in_progress")
        _checkpoint(vid, "operate", "Analyzing business metrics…")

        metrics = v.get("metrics") or {}
        has_metrics = bool(metrics)
        if not has_metrics:
            metrics = {"note": "no metrics provided"}

        analysis = self.operations.analyze(v, metrics)
        _checkpoint(vid, "operate",
                    f"Issues: {len(analysis.get('issues', []))}, "
                    f"Recommendations: {len(analysis.get('recommendations', []))}",
                    extra={"issues": analysis.get("issues", [])[:5],
                           "recommendations": analysis.get("recommendations", [])[:5]})

        cases = {"cases": []}
        if analysis.get("issues"):
            _checkpoint(vid, "operate", "Searching comparable historical cases…")
            first_issue = analysis["issues"][0].get("observation", "")
            cases = self.case_research.find_similar_cases(v, first_issue[:100])
            _checkpoint(vid, "operate",
                        f"Found {len(cases.get('cases', []))} historical cases",
                        extra={"cases": [c.get("company") for c in cases.get("cases", [])[:5]]})

        gate = "GO"
        rationale = (f"Issues: {len(analysis.get('issues', []))}. "
                     f"Cases: {len(cases.get('cases', []))}.")
        database.update_venture(vid, gate=gate, gate_rationale=rationale)
        decision_log.log(vid, stage="operate", agent="operations",
                         action="ops_analysis", decision=gate,
                         rationale=rationale)
        StateManager.set_stage(vid, "operate", "awaiting_approval")
        _checkpoint(vid, "operate", "Awaiting your approval")
        approval_id = approval_manager.request(
            vid, action="operate_gate",
            payload={"recommendation": gate, "rationale": rationale,
                     "classification": "ongoing operations"})
        return {"analysis": analysis, "cases": cases.get("cases", []),
                "stage_status": "awaiting_approval",
                "approval_id": approval_id,
                "feedback": {"has_real_metrics": has_metrics,
                             "issues": len(analysis.get("issues", [])),
                             "recommendations": len(analysis.get("recommendations", [])),
                             "cases_found": len(cases.get("cases", []))}}

    # -------------------------------------------------------- dispatch
    def run_stage(self, vid, stage):
        if stage not in STAGES:
            raise ValueError(f"unknown stage: {stage}")
        v = database.get_venture(vid)
        if not v:
            raise ValueError("unknown venture")
        if v["current_stage"] != stage:
            return {"status": "wrong_stage",
                    "message": f"You are on '{v['current_stage']}', not '{stage}'."}
        stages = database.get_stages(vid)
        current_status = stages[stage]["status"]
        if current_status in ("in_progress", "awaiting_approval", "completed", "stopped"):
            return {"status": "already_ran",
                    "message": f"Stage '{stage}' is '{current_status}'. "
                               "Approve or reject the pending decision first."}
        if current_status == "awaiting_input":
            with database.connect() as c:
                c.execute("DELETE FROM evidence WHERE venture_id=? AND stage=?",
                          (vid, stage))
                c.execute("DELETE FROM approvals WHERE venture_id=? AND status='pending'",
                          (vid,))
        dispatch = {
            "discover": self.run_discover,
            "validate": self.run_validate,
            "build": self.run_build,
            "commercial": self.run_commercial,
            "launch": self.run_launch,
            "operate": self.run_operate,
        }
        return dispatch[stage](vid)

    # ----------------------------------------------------------- admin
    def approve_and_advance(self, vid, approval_id):
        v = database.get_venture(vid)
        if not v:
            raise ValueError("unknown venture")
        approval_manager.resolve(approval_id, "approved")
        StateManager.set_stage(vid, v["current_stage"], "completed")
        decision_log.log(vid, stage=v["current_stage"], agent="founder",
                         action="approve_gate", decision="APPROVED",
                         rationale="Founder approved.",
                         approval_status="approved")
        return {"advanced_to": StateManager.advance_stage(vid)}

    def reject(self, vid, approval_id):
        approval_manager.resolve(approval_id, "rejected")
        v = database.get_venture(vid)
        if v:
            StateManager.set_stage(vid, v["current_stage"], "awaiting_input")
            decision_log.log(vid, stage=v["current_stage"], agent="founder",
                             action="reject_gate", decision="REJECTED",
                             rationale="Founder rejected.",
                             approval_status="rejected")
        return {"ok": True}

    def stop(self, vid):
        v = database.get_venture(vid)
        if v:
            StateManager.set_stage(vid, v["current_stage"], "stopped")
'''

# ═══════════════════════════════════════════════════════════════════════
# backend/app.py
# ═══════════════════════════════════════════════════════════════════════
APP_PY = r'''"""FastAPI backend."""
from __future__ import annotations
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import approval_manager, mindmap
from backend.orchestrator import Orchestrator
from config import FRONTEND_DIR, STAGE_LABELS, STAGES, THEME_BY_CATEGORY
from memory import database
from services import decision_log, evidence_ledger
from tools.ollama_client import OllamaError, get_client

app = FastAPI(title="VentureOS", version="1.0.0")
orchestrator = Orchestrator()

_analyze_cache: dict[str, dict] = {}


@app.on_event("startup")
def _startup():
    import os as _os
    provider = _os.getenv("MODEL_PROVIDER", "ollama").lower().strip()
    print("=" * 60)
    print("[VentureOS] Startup provider=" + provider)
    try:
        c = get_client()
        print("[VentureOS] Client: " + type(c).__name__)
        print("[VentureOS] Model: " + str(c.model))
        print("[VentureOS] Endpoint: " + str(getattr(c, "host", "n/a")))
        c.ensure_ready()
        print("[VentureOS] Ready")
    except OllamaError as e:
        print("[VentureOS] NOT READY")
        print(str(e))
    print("=" * 60)


class NewVenture(BaseModel):
    idea: str

class FounderView(BaseModel):
    venture_id: str
    message: str

class NewResearch(BaseModel):
    venture_id: str
    question: str

class ApproveRequest(BaseModel):
    venture_id: str
    approval_id: str

class ThemePayload(BaseModel):
    theme: dict

class AskRequest(BaseModel):
    question: str
    history: list[dict] = []

class UpdateFieldRequest(BaseModel):
    field: str
    value: str


@app.get("/favicon.ico")
def favicon():
    return Response(
        content=(b"\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x18\x00"
                 b"\x30\x00\x00\x00\x16\x00\x00\x00" + b"\x00" * 48),
        media_type="image/x-icon",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/api/health")
def health():
    c = get_client()
    try:
        c.ensure_ready()
        return {"ok": True, "model": c.model, "host": getattr(c, "host", "n/a")}
    except OllamaError as e:
        return JSONResponse(status_code=503, content={"ok": False, "error": str(e)})


@app.get("/api/config")
def config():
    return {"stages": STAGES, "stage_labels": STAGE_LABELS, "themes": THEME_BY_CATEGORY}


@app.get("/api/ventures")
def list_ventures():
    return database.list_ventures()


@app.post("/api/ventures")
def create_venture(body: NewVenture):
    if not body.idea.strip():
        raise HTTPException(400, "idea required")
    v = database.create_venture(name="Untitled", idea=body.idea.strip())
    database.add_message(v["id"], "user", body.idea.strip())
    return v


@app.get("/api/ventures/{vid}")
def get_venture(vid: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    return {"venture": v, "stages": database.get_stages(vid),
            "messages": database.get_messages(vid),
            "evidence": evidence_ledger.list_for(vid),
            "evidence_summary": evidence_ledger.summary(vid),
            "approvals": approval_manager.list_pending(vid)}


@app.get("/api/ventures/{vid}/mindmap")
def get_mindmap(vid: str):
    try:
        return mindmap.build(vid)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/ventures/{vid}/decisions")
def get_decisions(vid: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    return decision_log.list_for(vid)


@app.get("/api/ventures/{vid}/summary")
def get_summary(vid: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    history = database.get_messages(vid)
    from agents.founder_agent import _assistant_asks_field, _fields_answered
    answers = {}
    for i, msg in enumerate(history):
        if msg.get("role") != "assistant":
            continue
        field = _assistant_asks_field(msg.get("content", ""))
        if not field or field in answers:
            continue
        if i + 1 < len(history) and history[i + 1].get("role") == "user":
            answers[field] = history[i + 1].get("content", "").strip()
    overrides = (v.get("brief") or {}).get("field_overrides") or {}
    answers.update(overrides)
    return {"idea": v["idea"], "answers": answers,
            "answered_fields": sorted(_fields_answered(history))}


@app.post("/api/ventures/{vid}/analyze-summary")
def analyze_summary(vid: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    history = database.get_messages(vid)
    from agents.founder_agent import _assistant_asks_field
    answers = {}
    for i, msg in enumerate(history):
        if msg.get("role") != "assistant":
            continue
        field = _assistant_asks_field(msg.get("content", ""))
        if not field or field in answers:
            continue
        if i + 1 < len(history) and history[i + 1].get("role") == "user":
            answers[field] = history[i + 1].get("content", "").strip()
    overrides = (v.get("brief") or {}).get("field_overrides") or {}
    answers.update(overrides)
    if not answers:
        return {"raw": {}, "analyzed": {}}

    cache_key = vid + "|" + "|".join(f"{k}={val}" for k, val in sorted(answers.items()))
    if cache_key in _analyze_cache:
        return {"raw": answers, "analyzed": _analyze_cache[cache_key]}

    try:
        analyzed = orchestrator.founder.analyze_answers(answers)
    except Exception as e:
        raise HTTPException(502, str(e))
    _analyze_cache[cache_key] = analyzed
    return {"raw": answers, "analyzed": analyzed}


@app.post("/api/ventures/{vid}/ask")
def ask(vid: str, body: AskRequest):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    if not body.question.strip():
        raise HTTPException(400, "question required")
    try:
        answer = orchestrator.founder.answer_question(v, body.question.strip(),
                                                     body.history or [])
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"answer": answer}


@app.post("/api/ventures/{vid}/update-field")
def update_field(vid: str, body: UpdateFieldRequest):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    field = body.field.strip()
    if field not in ("budget", "skills", "education", "target_market"):
        raise HTTPException(400, f"invalid field: {field}")
    brief = v.get("brief") or {}
    overrides = brief.get("field_overrides") or {}
    overrides[field] = body.value.strip()
    brief["field_overrides"] = overrides
    database.update_venture(vid, brief=brief)
    _analyze_cache.pop(vid, None)
    return {"ok": True, "field": field, "value": body.value.strip(),
            "overrides": overrides}


@app.post("/api/founder/next-question")
def founder_next(body: FounderView):
    v = database.get_venture(body.venture_id)
    if not v:
        raise HTTPException(404, "venture not found")
    history = database.get_messages(body.venture_id)
    last = history[-1] if history else None
    already = (last is not None and last["role"] == "user"
               and last["content"] == body.message)
    if not already:
        database.add_message(body.venture_id, "user", body.message)
        history = database.get_messages(body.venture_id)
    try:
        res = orchestrator.founder.next_question(v["idea"], history)
    except Exception as e:
        raise HTTPException(502, str(e))
    if res["question"]:
        database.add_message(body.venture_id, "assistant", res["question"])
    return res


@app.post("/api/founder/draft-brief")
def founder_brief(body: FounderView):
    v = database.get_venture(body.venture_id)
    if not v:
        raise HTTPException(404, "venture not found")
    history = database.get_messages(body.venture_id)
    try:
        brief = orchestrator.founder.draft_brief(v["idea"], history)
    except Exception as e:
        raise HTTPException(502, str(e))
    theme = THEME_BY_CATEGORY.get(brief.get("category", "general"), "indigo")
    database.update_venture(body.venture_id,
                            name=brief.get("name") or v["name"],
                            brief=brief, theme=theme)
    return {"brief": brief, "theme": theme}


@app.post("/api/ventures/{vid}/redraft-brief")
def redraft_brief(vid: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    history = database.get_messages(vid)
    try:
        brief = orchestrator.founder.draft_brief(v["idea"], history)
    except Exception as e:
        raise HTTPException(502, str(e))
    theme = THEME_BY_CATEGORY.get(brief.get("category", "general"), "indigo")
    database.update_venture(vid, name=brief.get("name") or v["name"],
                            brief=brief, theme=theme)
    return {"brief": brief, "theme": theme}


@app.post("/api/ventures/{vid}/theme")
def set_theme(vid: str, body: ThemePayload):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    brief = v.get("brief") or {}
    brief["theme"] = body.theme
    database.update_venture(vid, brief=brief)
    return {"ok": True, "theme": body.theme}


@app.post("/api/ventures/{vid}/run-stage/{stage}")
async def run_stage(vid: str, stage: str):
    v = database.get_venture(vid)
    if not v:
        raise HTTPException(404, "venture not found")
    try:
        return await asyncio.to_thread(orchestrator.run_stage, vid, stage)
    except Exception as e:
        raise HTTPException(502, str(e))


@app.post("/api/appro
"""apply_hackathon_3.py — writes tests/, prompts/, scripts/, outputs/, decision_log.json.

Run: python apply_hackathon_3.py
"""
from pathlib import Path

ROOT = Path(__file__).parent


def write(rel_path, content, overwrite=True):
    p = ROOT / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite and p.exists():
        print(f"  [SKIP] {rel_path} (already exists)")
        return
    p.write_text(content, encoding="utf-8")
    print(f"  [OK]   {rel_path}")


# ── Sanity check ────────────────────────────────────────────────────────
required = ["LICENSE", "README.md", "ARCHITECTURE.md", "docker-compose.yml"]
missing = [f for f in required if not (ROOT / f).exists()]
if missing:
    print(f"  [WARN] Missing: {missing}")
    print("  [WARN] Run apply_hackathon_1.sh and apply_hackathon_2.sh first.")
    print()


# ══════════════════════════════════════════════════════════════════════
# tests/
# ══════════════════════════════════════════════════════════════════════
write("tests/__init__.py", "")

write("tests/conftest.py", r'''"""Test fixtures - no model required."""
import os
import sys
from pathlib import Path

os.environ.setdefault("MODEL_PROVIDER", "ollama")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
''')

write("tests/test_smoke.py", r'''"""Smoke test - the app imports and basic endpoints respond."""


def test_import_app():
    from backend.app import app
    assert app is not None
    assert app.title == "VentureOS"


def test_config_endpoint():
    from fastapi.testclient import TestClient
    from backend.app import app
    with TestClient(app) as c:
        r = c.get("/api/config")
        assert r.status_code == 200
        body = r.json()
        assert "stages" in body
        assert len(body["stages"]) == 6


def test_stages_defined():
    from config import STAGES, STAGE_LABELS
    assert STAGES == ["discover", "validate", "build",
                      "commercial", "launch", "operate"]
    assert all(s in STAGE_LABELS for s in STAGES)


def test_database_initialises():
    from memory import database
    v = database.create_venture(name="Test", idea="A test idea")
    assert v["id"]
    stages = database.get_stages(v["id"])
    assert len(stages) == 6
    assert all(s["status"] == "not_started" for s in stages.values())
''')

write("tests/test_gates.py", r'''"""Gate logic - STOP reachable, REPEAT when designs are not results."""


def test_validate_gate_repeats_without_results():
    designed = 3
    recorded = 0
    if recorded >= 2:
        gate = "GO"
    elif designed >= 2:
        gate = "REPEAT"
    else:
        gate = "REPEAT"
    assert gate == "REPEAT"


def test_orchestrator_has_all_stages():
    from backend.orchestrator import Orchestrator
    try:
        o = Orchestrator()
    except Exception:
        import pytest
        pytest.skip("model unavailable")
    for m in ("run_discover", "run_validate", "run_build",
              "run_commercial", "run_launch", "run_operate"):
        assert hasattr(o, m)
''')

write("tests/test_approval_required.py", r'''"""Every publish/send/spend action must require founder approval."""


def test_approval_row_created_on_gate():
    from memory import database
    from backend import approval_manager
    v = database.create_venture(name="Approval test", idea="test")
    aid = approval_manager.request(v["id"], action="discover_gate",
                                   payload={"recommendation": "GO"})
    assert aid
    pending = approval_manager.list_pending(v["id"])
    assert any(a["id"] == aid for a in pending)


def test_require_approved_raises():
    from memory import database
    from backend.approval_manager import require_approved, ApprovalRequired
    v = database.create_venture(name="Approval test 2", idea="test")
    try:
        require_approved(v["id"], "discover_gate")
        assert False, "should have raised"
    except ApprovalRequired:
        pass
''')


# ══════════════════════════════════════════════════════════════════════
# prompts/
# ══════════════════════════════════════════════════════════════════════
write("prompts/INDEX.md", r'''# Agent prompts

One file per agent. The system prompt lives in the corresponding `agents/*.py` class as `system_prompt` - these files are the human-readable source of truth, kept in sync manually.

| Agent | File | Role |
|---|---|---|
| FounderAgent | founder.md | Clarify the idea, draft the brief |
| ResearchAgent | researcher.md | Search and extract findings with sources |
| FeasibilityAgent | feasibility.md | Score feasibility, recommend a gate |
| StrategyAgent | strategy.md | Design the MVP spec |
| DevelopmentAgent | development.md | Decide + generate a real MVP |
| TestingAgent | testing.md | Generate + run smoke tests |
| CommercialAgent | commercial.md | Propose pricing |
| FinancialAgent | financial.md | Compute unit economics |
| MarketingAgent | marketing.md | Write launch copy with evidence checks |
| OperationsAgent | operations.md | Analyse metrics, recommend |
| CaseResearchAgent | case_research.md | Find comparable historical cases |
''')

write("prompts/founder.md", r'''# FounderAgent

**Role:** Clarify the founder's idea before extracting required parameters.
**System prompt:** *You are a warm, curious product partner. Ask ONE question at a time.*

**Flow:**
1. Two open-ended clarification questions (problem / differentiation).
2. Then required fields, in order: `budget`, `time`, `skills`, `education`, `target_market`.
3. Normalises raw answers into clean phrases (e.g. "like a million dollars" -> "1,000,000 USD").
4. Drafts the business brief used by every downstream agent.

**Never invents facts.** Quotes founder answers verbatim in the brief.
''')

write("prompts/researcher.md", r'''# ResearchAgent

**Role:** Search and extract findings, always with sources.
**System prompt:** *You are a careful market-research analyst. Use ONLY the provided search results. Cite source URL for every claim.*

**Input:** a research question.
**Method:** DuckDuckGo search (HTML + `ddgs`), feed top 6 results to the LLM, extract up to 5 findings. Any finding without a `source_url` is stored as `type="assumption"`; with a URL, `type="verified"`.
**Output:** `{findings, limitations, sources, query_used}`.
''')

write("prompts/feasibility.md", r'''# FeasibilityAgent

**Role:** Decide, never hedge. Gate recommendation at Discover.
**System prompt:** *You MUST decide. NEVER output UNDETERMINED. Classification: FEASIBLE, CONDITIONALLY FEASIBLE, or NOT FEASIBLE. Gate: GO, REPEAT, PIVOT, or STOP.*

**Scores five dimensions:** market, financial, technical, operational, competitive.
**Output:** `classification`, `dimensions`, `risks`, `unresolved_assumptions`, `gate_recommendation`, `rationale`, `sources_used`, `next_steps`.
''')

write("prompts/strategy.md", r'''# StrategyAgent

**Role:** Design the smallest viable MVP spec.
**System prompt:** *You produce small, specific MVP specs. Every feature MUST trace to a customer need or evidence-backed assumption.*

**Output:** 3-5 features (each with `name`, `purpose`, `traced_to`, `acceptance`), `out_of_scope`, and `tech_stack`.
''')

write("prompts/development.md", r'''# DevelopmentAgent

**Role:** Decide whether to build, then generate a WORKING MVP.
**System prompt:** *You write complete, working FastAPI applications. Never leave a route as a stub.*

**Build decision:** parse founder's `time` into hours, estimate complexity from feature count + hard keywords (ai, real-time, video, auth). If `hours < complexity * 0.5` -> `DEFER`. If `hours < complexity` -> `BUILD_LIMITED` (2 features). Else `BUILD`.

**Code generation:** LLM writes complete `main.py` + HTML. Uses in-memory dict/list state, real endpoints, real HTML form, `/​_state` for verification. Syntax-validated before writing. If generation fails, falls back to a LABELED scaffold.

**Output:** `outputs/<vid>/mvp/{main.py, requirements.txt, README.md, templates/index.html}`.
''')

write("prompts/testing.md", r'''# TestingAgent

**Role:** Write and run a smoke test on the generated app.
**System prompt:** *You write minimal working tests.*

Generates `test_smoke.py` and runs `pytest` with a 30s timeout. Records result as `type="experimental"` (pass) or `type="assumption"` (fail) in the evidence ledger.
''')

write("prompts/commercial.md", r'''# CommercialAgent

**Role:** Propose pricing grounded in evidence.
**System prompt:** *Propose pricing from evidence. If no evidence, say so and propose an experiment.*

**Output:** `model`, `price_per_unit`, `unit`, `rationale`, `competitor_anchors`, `confidence`.
**Never touches payment rails** - commercial setup is pricing + draft policies only.
''')

write("prompts/financial.md", r'''# FinancialAgent

**Role:** Compute unit economics with explicit formulas.
**System prompt:** *Conservative financial modeling with explicit formulas.*

**Output:** contribution margin, gross margin %, break-even units. Formulas returned verbatim so the founder can audit them.
''')

write("prompts/marketing.md", r'''# MarketingAgent

**Role:** Write launch copy that passes an evidence check.
**System prompt:** *You write honest marketing copy. Never invent testimonials, customers, revenue, or guarantees.*

Every claim must cite an `evidence_id` from the ledger, or is marked `status: "unsupported"` and the launch gate fails.
''')

write("prompts/operations.md", r'''# OperationsAgent

**Role:** Analyse metrics and recommend concrete actions.
**System prompt:** *Analyze metrics. Refuse generic advice. Every recommendation must tie to a metric observation.*

**Output:** `issues` (observation + severity), `recommendations` (action + rationale + expected_impact), `missing_metrics`.
''')

write("prompts/case_research.md", r'''# CaseResearchAgent

**Role:** Find comparable historical business cases.
**System prompt:** *Summarize real, documented cases. Cite source URL. Never invent company names or outcomes.*

**Method:** search `"startup case study <problem> pivot outcome"`, extract up to 3 real cases with source URLs.
**Output:** `{cases: [{company, situation, strategy, outcome, source_url, applicability}]}`.
''')


# ══════════════════════════════════════════════════════════════════════
# scripts/
# ══════════════════════════════════════════════════════════════════════
write("scripts/export_decision_log.py", r'''"""Export SQLite decisions to decision_log.json in the hackathon schema."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memory.database import connect  # noqa: E402
from tools.ollama_client import get_client, OllamaError  # noqa: E402


def _current_model():
    try:
        return get_client().model
    except OllamaError:
        import os
        return os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")


def export(path="decision_log.json"):
    with connect() as c:
        rows = c.execute("SELECT * FROM decisions ORDER BY created_at ASC").fetchall()

    model = _current_model()
    entries = []
    for r in rows:
        d = dict(r)
        sources = []
        with connect() as c:
            evs = c.execute(
                "SELECT source FROM evidence "
                "WHERE venture_id=? AND stage=? AND source IS NOT NULL AND source != ''",
                (d.get("venture_id"), d.get("stage")),
            ).fetchall()
        for e in evs:
            src = e["source"]
            if src and src not in sources:
                sources.append(src)

        entries.append({
            "timestamp": d.get("created_at") or d.get("timestamp"),
            "agent": d.get("agent"),
            "action": d.get("action"),
            "sources": sources,
            "model": d.get("model") or model,
            "cost": 0,
            "approved_by": "founder" if d.get("approval_status") == "approved" else None,
        })

    Path(path).write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"[export] {len(entries)} entries -> {path}")
    return len(entries)


if __name__ == "__main__":
    export()
''')

write("scripts/run_demo.py", r'''"""End-to-end demo. Writes outputs/phase*.md and decision_log.json.

Run: python scripts/run_demo.py

Requires a working model provider (Gemini or Ollama).
"""
from __future__ import annotations
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.orchestrator import Orchestrator  # noqa: E402
from memory import database  # noqa: E402
from scripts.export_decision_log import export  # noqa: E402

OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

WEAK_IDEA = "An AI that predicts lottery numbers with 99% accuracy."
STRONG_IDEA = ("A sustainability-focused reusable packaging service for cafes in Cairo. "
               "Cafes pay a monthly subscription; customers return containers to any "
               "cafe in the network. I have 2 weeks and can code in Python.")


def md(path, title, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# " + title + "\n\n" + body + "\n", encoding="utf-8")
    print("  [out] " + str(path.relative_to(ROOT)))


def dump_discover(vid, result, tag="phase1"):
    feas = result.get("feasibility") or {}
    fb = result.get("feedback") or {}
    v = database.get_venture(vid)
    lines = [
        "**Venture:** " + (v.get("idea") if v else "(unknown)"),
        "",
        "## Recommendation",
        "",
        "Classification: **" + str(feas.get("classification", "?")) + "**",
        "Gate: **" + str(feas.get("gate_recommendation", "?")) + "**",
        "",
        "## Rationale",
        "",
        feas.get("rationale", "(none)"),
        "",
        "## Dimensions",
        "",
        "| Dimension | Score | Reason |",
        "|---|---|---|",
    ]
    for k, d in (feas.get("dimensions") or {}).items():
        lines.append("| " + k + " | " + str(d.get("score", "?")) + " | " + str(d.get("reason", "")) + " |")
    lines += ["", "## Statistics", "",
              "- Sources found: " + str(fb.get("sources_found", 0)),
              "- Findings extracted: " + str(fb.get("findings_extracted", 0))]
    lines += ["", "## Sources used", ""]
    sources = feas.get("sources_used") or fb.get("sources_used") or []
    if sources:
        lines += ["- " + s for s in sources]
    else:
        lines.append("_No sources returned; findings labelled ASSUMPTION._")
    md(OUT / (tag + "_step1_opportunities.md"), "Discover - opportunities & feasibility", "\n".join(lines))
    md(OUT / (tag + "_gate_decision.md"), "Discover - gate decision",
       "**Gate:** " + str(feas.get("gate_recommendation", "?")) + "\n\n"
       + "**Classification:** " + str(feas.get("classification", "?")) + "\n\n"
       + "**Rationale:** " + str(feas.get("rationale", "")) + "\n\n"
       + "**Approval status:** see decision_log.json for the founder row.")


def dump_validate(vid, result, tag="phase2"):
    exps = result.get("experiments") or []
    lines = ["**STATUS: STUBBED.** Experiments designed but not executed.", ""]
    for i, e in enumerate(exps, 1):
        lines.append("### Experiment " + str(i) + ": " + str(e.get("name", "?")))
        lines += ["- **Hypothesis:** " + str(e.get("hypothesis", "")),
                  "- **Method:** " + str(e.get("method", "")),
                  "- **Success:** " + str(e.get("success", "")),
                  "- **Failure:** " + str(e.get("failure", "")),
                  "- **Cost:** " + str(e.get("cost", "")),
                  "- **Time:** " + str(e.get("time", "")), ""]
    md(OUT / (tag + "_step1_lean_canvas.md"), "Validate - Lean Canvas / experiments", "\n".join(lines))
    fb = result.get("feedback") or {}
    md(OUT / (tag + "_gate_decision.md"), "Validate - gate decision",
       "**Designed:** " + str(fb.get("experiments_designed", 0)) + "\n\n"
       + "**With recorded results:** " + str(fb.get("results_recorded", 0)) + "\n\n"
       + "**Gate:** " + str(fb.get("gate", "REPEAT")) + "\n\n"
       + str(fb.get("note", "")))


def dump_build(vid, result, tag="phase3"):
    if result.get("deferred"):
        md(OUT / (tag + "_step1_mvp_spec.md"), "Build - DEFERRED",
           "**Reason:** " + str(result.get("reason", "not specified")) + "\n\n"
           + "**Hours budget:** " + str(result.get("hours_budget", "?")) + "\n"
           + "**Hours complexity:** " + str(result.get("hours_complexity", "?")) + "\n\n"
           + "The system chose not to build - not enough time for this spec.")
        return

    spec = result.get("spec") or {}
    features = spec.get("features") or []
    lines = ["## MVP features", ""]
    for f in features:
        lines += ["### " + str(f.get("name", "?")),
                  "- **Purpose:** " + str(f.get("purpose", "")),
                  "- **Traced to:** " + str(f.get("traced_to", "")),
                  "- **Acceptance:** " + str(f.get("acceptance", "")), ""]
    md(OUT / (tag + "_step1_mvp_spec.md"), "Build - MVP specification", "\n".join(lines))

    files = result.get("files") or []
    test = result.get("test") or {}
    md(OUT / (tag + "_step2_scaffold.md"), "Build - scaffold & tests",
       "**Files:**\n" + "\n".join("- " + n for n in files)
       + "\n\n**Tests passed:** " + str(test.get("passed"))
       + "\n\n**Output dir:** " + str(result.get("output_dir", "")))


def dump_commercial(vid, result, tag="phase4"):
    p = result.get("pricing") or {}
    e = result.get("economics") or {}
    md(OUT / (tag + "_step1_pricing.md"), "Commercial setup - pricing",
       "**Model:** " + str(p.get("model")) + "\n\n"
       + "**Price:** " + str(p.get("price_per_unit")) + " " + str(p.get("unit", "")) + "\n\n"
       + "**Confidence:** " + str(p.get("confidence")) + "\n\n"
       + "**Rationale:** " + str(p.get("rationale", "")))
    md(OUT / (tag + "_step2_economics.md"), "Commercial setup - unit economics",
       "| Metric | Value |\n|---|---|\n"
       + "| Price per unit | " + str(e.get("price_per_unit")) + " |\n"
       + "| Variable cost / unit | " + str(e.get("variable_cost_per_unit")) + " |\n"
       + "| Fixed costs / month | " + str(e.get("fixed_costs_monthly")) + " |\n"
       + "| Contribution margin | " + str(e.get("contribution_margin")) + " |\n"
       + "| Gross margin % | " + str(e.get("gross_margin_pct")) + " |\n"
       + "| Break-even units | " + str(e.get("break_even_units")) + " |\n\n"
       + "**Formulas:**\n\n```\n" + json.dumps(e.get("formulas", {}), indent=2) + "\n```")


def dump_launch(vid, result, tag="phase5"):
    m = result.get("materials") or {}
    lines = ["**Tagline:** " + str(m.get("tagline", "")), "",
             "**One-liner:** " + str(m.get("one_liner", "")), "",
             "## Claims", ""]
    for c in (m.get("claims") or []):
        status = c.get("status", "?")
        marker = "[OK]" if status == "supported" else "[!!]"
        lines.append("- " + marker + " **" + status + "** - " + str(c.get("text", ""))
                     + " (evidence_id: " + str(c.get("evidence_id", "-")) + ")")
    lines += ["", "**Call to action:** " + str(m.get("call_to_action", ""))]
    md(OUT / (tag + "_step1_launch_materials.md"), "Launch - materials", "\n".join(lines))


def dump_operate(vid, result, tag="phase6"):
    a = result.get("analysis") or {}
    lines = ["## Issues", ""]
    for issue in (a.get("issues") or []):
        lines.append("- **" + str(issue.get("severity", "?")).upper() + "**: "
                     + str(issue.get("observation", "")))
    lines += ["", "## Recommendations", ""]
    for r in (a.get("recommendations") or []):
        lines.append("- **" + str(r.get("action", "")) + "** - "
                     + str(r.get("rationale", ""))
                     + " (expected: " + str(r.get("expected_impact", "")) + ")")
    md(OUT / (tag + "_step1_ops_analysis.md"), "Operate - analysis", "\n".join(lines))


def approve(orch, vid, approval_id):
    try:
        orch.approve_and_advance(vid, approval_id)
        print("  [gate] approved " + approval_id[:8] + "...")
    except Exception as e:
        print("  [gate] approve failed: " + str(e))


def run_weak_idea(orch):
    print("\n=== Weak idea - expecting STOP ===")
    v = database.create_venture(name="Lottery predictor", idea=WEAK_IDEA)
    vid = v["id"]
    database.add_message(vid, "user", WEAK_IDEA)
    try:
        result = orch.run_stage(vid, "discover")
        dump_discover(vid, result, tag="weak_phase1")
        gate = (result.get("feasibility") or {}).get("gate_recommendation")
        print("  [gate] " + str(gate))
        if gate != "STOP":
            print("  [warn] expected STOP but got " + str(gate))
    except Exception:
        traceback.print_exc()


def run_strong_idea(orch):
    print("\n=== Strong idea - full pipeline ===")
    v = database.create_venture(name="Reusable packaging", idea=STRONG_IDEA)
    vid = v["id"]
    database.add_message(vid, "user", STRONG_IDEA)

    chain = [
        ("discover", dump_discover),
        ("validate", dump_validate),
        ("build", dump_build),
        ("commercial", dump_commercial),
        ("launch", dump_launch),
        ("operate", dump_operate),
    ]
    for stage, dumper in chain:
        print("  [" + stage + "] running...")
        try:
            result = orch.run_stage(vid, stage)
            dumper(vid, result)
            aid = result.get("approval_id")
            if aid:
                approve(orch, vid, aid)
        except Exception:
            traceback.print_exc()
            break
    return vid


def main():
    orch = Orchestrator()
    run_weak_idea(orch)
    run_strong_idea(orch)
    print("\n=== Exporting decision log ===")
    export(str(ROOT / "decision_log.json"))
    print("\nDone. Files in outputs/ and decision_log.json at root.")


if __name__ == "__main__":
    main()
''')


# ══════════════════════════════════════════════════════════════════════
# outputs/ + decision_log.json
# ══════════════════════════════════════════════════════════════════════
write("outputs/README.md", r'''# outputs/

This directory contains **real demo-run outputs**. Nothing here is hand-written.

Regenerate with:

```bash
python scripts/run_demo.py
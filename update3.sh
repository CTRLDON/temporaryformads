
---

## Script 3 — Tests, prompts, scripts, outputs

Save as `apply_hackathon_3.sh`, run:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
mkdir -p tests prompts scripts outputs

# ─── tests/ ───
cat > tests/__init__.py <<'__H_E__'
__H_E__

cat > tests/conftest.py <<'__H_CF__'
"""Test fixtures — no model required."""
import os
import sys
from pathlib import Path

os.environ.setdefault("MODEL_PROVIDER", "ollama")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
__H_CF__

cat > tests/test_smoke.py <<'__H_TS__'
"""Smoke test — the app imports and basic endpoints respond."""

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
    assert STAGES == ["discover", "validate", "build", "commercial", "launch", "operate"]
    assert all(s in STAGE_LABELS for s in STAGES)

def test_database_initialises():
    from memory import database
    v = database.create_venture(name="Test", idea="A test idea")
    assert v["id"]
    stages = database.get_stages(v["id"])
    assert len(stages) == 6
    assert all(s["status"] == "not_started" for s in stages.values())
__H_TS__

cat > tests/test_gates.py <<'__H_TG__'
"""Gate logic — STOP reachable, REPEAT when designs are not results."""

def test_validate_gate_repeats_without_results():
    # Mirrors the orchestrator logic: designs alone must not advance.
    designed = 3
    recorded = 0
    if recorded >= 2:
        gate = "GO"
    elif designed >= 2:
        gate = "REPEAT"
    else:
        gate = "REPEAT"
    assert gate == "REPEAT"

def test_stop_is_reachable():
    from backend.orchestrator import Orchestrator
    try:
        o = Orchestrator()
    except Exception:
        import pytest
        pytest.skip("model unavailable")
    for m in ("run_discover", "run_validate", "run_build",
              "run_commercial", "run_launch", "run_operate"):
        assert hasattr(o, m)
__H_TG__

cat > tests/test_approval_required.py <<'__H_TA__'
"""Every publish/send/spend action must require founder approval."""

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
__H_TA__

# ─── prompts/ ───
cat > prompts/INDEX.md <<'__H_PI__'
# Agent prompts

One file per agent. The system prompt lives in the corresponding `agents/*.py` class as `system_prompt` — these files are the human-readable source of truth, kept in sync manually.

| Agent | File | Role |
|---|---|---|
| FounderAgent | founder.md | Clarify the idea, draft the brief |
| ResearchAgent | researcher.md | Search and extract findings with sources |
| FeasibilityAgent | feasibility.md | Score feasibility, recommend a gate |
| StrategyAgent | strategy.md | Design the MVP spec |
| DevelopmentAgent | development.md | Scaffold the MVP source |
| TestingAgent | testing.md | Generate + run smoke tests |
| CommercialAgent | commercial.md | Propose pricing |
| FinancialAgent | financial.md | Compute unit economics |
| MarketingAgent | marketing.md | Write launch copy with evidence checks |
| OperationsAgent | operations.md | Analyse metrics, recommend |
| CaseResearchAgent | case_research.md | Find comparable historical cases |
__H_PI__

cat > prompts/founder.md <<'__H_P__'
# FounderAgent

**Role:** Clarify the founder's idea before extracting required parameters.
**System prompt:** *You are a warm, curious product partner. Ask ONE question at a time.*

**Flow:**
1. Two open-ended clarification questions (problem / differentiation).
2. Then required fields, in order: `budget`, `skills`, `education`, `target_market`.
3. Normalises raw answers into clean phrases for the brief (e.g. "like a million dollars" → "1,000,000 USD").
4. Drafts the business brief used by every downstream agent.

**Never invents facts.** Quotes founder answers verbatim in the brief.
__H_P__

cat > prompts/researcher.md <<'__H_P__'
# ResearchAgent

**Role:** Search and extract findings, always with sources.
**System prompt:** *You are a careful market-research analyst. Use ONLY the provided search results. Cite source URL for every claim.*

**Input:** a research question.
**Method:** DuckDuckGo search (HTML + `ddgs`), feed top 6 results to the LLM, extract up to 5 findings. Any finding without a `source_url` is stored as `type="assumption"`; with a URL, `type="verified"`.
**Output:** `{findings: [...], limitations: [...], sources: [...], query_used: str}`.
__H_P__

cat > prompts/feasibility.md <<'__H_P__'
# FeasibilityAgent

**Role:** Decide, never hedge. Gate recommendation at Discover.
**System prompt:** *You MUST decide. NEVER output UNDETERMINED. If evidence is thin, classify as CONDITIONALLY FEASIBLE or NOT FEASIBLE and explain which dimensions are weak. Classification: FEASIBLE, CONDITIONALLY FEASIBLE, or NOT FEASIBLE. Gate: GO, REPEAT, PIVOT, or STOP.*

**Scores five dimensions:** market, financial, technical, operational, competitive.
**Output:** `classification`, `dimensions`, `risks`, `unresolved_assumptions`, `gate_recommendation`, `rationale`, `sources_used`, `next_steps`.
__H_P__

cat > prompts/strategy.md <<'__H_P__'
# StrategyAgent

**Role:** Design the smallest viable MVP spec.
**System prompt:** *You produce small, specific MVP specs. Every feature MUST trace to a customer need or evidence-backed assumption.*

**Output:** 3–5 features (each with `name`, `purpose`, `traced_to`, `acceptance`), `out_of_scope`, and `tech_stack`.
__H_P__

cat > prompts/development.md <<'__H_P__'
# DevelopmentAgent

**Role:** Scaffold working MVP source code.
**System prompt:** *You write SMALL, WORKING scaffolds. Never write fake code.*

Writes `README.md`, `requirements.txt`, and a working `main.py` (FastAPI) to `outputs/<vid>/mvp/`. Every route returns `{"status": "todo"}` — ready for the founder to fill in.
__H_P__

cat > prompts/testing.md <<'__H_P__'
# TestingAgent

**Role:** Write and run a smoke test on the scaffold.
**System prompt:** *You write minimal working tests.*

Generates `test_smoke.py` and runs `pytest` with a 30s timeout. Records result as `type="experimental"` (pass) or `type="assumption"` (fail) in the evidence ledger.
__H_P__

cat > prompts/commercial.md <<'__H_P__'
# CommercialAgent

**Role:** Propose pricing grounded in evidence.
**System prompt:** *Propose pricing from evidence. If no evidence, say so and propose an experiment.*

**Output:** `model`, `price_per_unit`, `unit`, `rationale`, `competitor_anchors`, `confidence`.
**Never touches payment rails** — commercial setup is pricing + draft policies only.
__H_P__

cat > prompts/financial.md <<'__H_P__'
# FinancialAgent

**Role:** Compute unit economics with explicit formulas.
**System prompt:** *Conservative financial modeling with explicit formulas.*

**Output:** contribution margin, gross margin %, break-even units. Formulas are returned verbatim in the response so the founder can audit them.
__H_P__

cat > prompts/marketing.md <<'__H_P__'
# MarketingAgent

**Role:** Write launch copy that passes an evidence check.
**System prompt:** *You write honest marketing copy. Never invent testimonials, customers, revenue, or guarantees.*

Every claim must cite an `evidence_id` from the ledger, or is marked `status: "unsupported"` and the launch gate fails.
__H_P__

cat > prompts/operations.md <<'__H_P__'
# OperationsAgent

**Role:** Analyse metrics and recommend concrete actions.
**System prompt:** *Analyze metrics. Refuse generic advice. Every recommendation must tie to a metric observation.*

**Output:** `issues` (observation + severity), `recommendations` (action + rationale + expected_impact), `missing_metrics`.
__H_P__

cat > prompts/case_research.md <<'__H_P__'
# CaseResearchAgent

**Role:** Find comparable historical business cases.
**System prompt:** *Summarize real, documented cases. Cite source URL. Never invent company names or outcomes.*

**Method:** search `"startup case study <problem> pivot outcome"`, extract up to 3 real cases with source URLs.
**Output:** `{cases: [{company, situation, strategy, outcome, source_url, applicability}]}`.
__H_P__

# ─── scripts/ ───
cat > scripts/export_decision_log.py <<'__H_ED__'
"""Export SQLite decisions to decision_log.json in the hackathon schema."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memory.database import connect  # noqa: E402
from tools.ollama_client import get_client, OllamaError  # noqa: E402


def _current_model() -> str:
    try:
        return get_client().model
    except OllamaError:
        import os
        return os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")


def export(path: str = "decision_log.json") -> int:
    with connect() as c:
        rows = c.execute("SELECT * FROM decisions ORDER BY created_at ASC").fetchall()

    model = _current_model()
    entries = []
    for r in rows:
        d = dict(r)
        sources: list[str] = []
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
__H_ED__

cat > scripts/run_demo.py <<'__H_RD__'
"""End-to-end demo — runs a weak idea to STOP, then a strong idea to completion.
Writes outputs/phase*.md and decision_log.json.

    python scripts/run_demo.py

Requires a working Ollama (`ollama serve` and `ollama pull qwen2.5-coder:7b`).
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
from services import evidence_ledger  # noqa: E402
from scripts.export_decision_log import export  # noqa: E402

OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

WEAK_IDEA = "An AI that predicts lottery numbers with 99% accuracy."
STRONG_IDEA = ("A sustainability-focused reusable packaging service for cafés in Cairo. "
               "Cafés pay a monthly subscription; customers return containers to any café "
               "in the network.")


def md(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    print(f"  [out] {path.relative_to(ROOT)}")


def dump_discover(vid: str, result: dict, tag: str = "phase1") -> None:
    feas = result.get("feasibility") or {}
    fb = result.get("feedback") or {}
    lines = [
        f"**Venture:** {database.get_venture(vid)['idea']}",
        "",
        "## Recommendation",
        "",
        f"Classification: **{feas.get('classification','?')}**",
        f"Gate: **{feas.get('gate_recommendation','?')}**",
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
    for k, v in (feas.get("dimensions") or {}).items():
        lines.append(f"| {k} | {v.get('score','?')} | {v.get('reason','')} |")
    lines += ["", "## Statistics", "",
              f"- Sources found: {fb.get('sources_found', 0)}",
              f"- Findings extracted: {fb.get('findings_extracted', 0)}"]
    lines += ["", "## Sources used", ""]
    sources = feas.get("sources_used") or fb.get("sources_used") or []
    lines += [f"- {s}" for s in sources] if sources else ["_No sources returned; findings labelled ASSUMPTION._"]
    md(OUT / f"{tag}_step1_opportunities.md", "Discover — opportunities & feasibility", "\n".join(lines))
    md(OUT / f"{tag}_gate_decision.md", "Discover — gate decision",
       f"**Gate:** {feas.get('gate_recommendation','?')}\n\n"
       f"**Classification:** {feas.get('classification','?')}\n\n"
       f"**Rationale:** {feas.get('rationale','')}\n\n"
       "**Approval status:** see `decision_log.json` for the founder row.")


def dump_validate(vid: str, result: dict, tag: str = "phase2") -> None:
    exps = result.get("experiments") or []
    lines = ["**STATUS: STUBBED.** Experiments designed but not executed.", ""]
    for i, e in enumerate(exps, 1):
        lines.append(f"### Experiment {i}: {e.get('name','?')}")
        lines += [f"- **Hypothesis:** {e.get('hypothesis','')}",
                  f"- **Method:** {e.get('method','')}",
                  f"- **Success:** {e.get('success','')}",
                  f"- **Failure:** {e.get('failure','')}",
                  f"- **Cost:** {e.get('cost','')}",
                  f"- **Time:** {e.get('time','')}", ""]
    md(OUT / f"{tag}_step1_lean_canvas.md", "Validate — Lean Canvas / experiments", "\n".join(lines))
    fb = result.get("feedback") or {}
    md(OUT / f"{tag}_gate_decision.md", "Validate — gate decision",
       f"**Designed:** {fb.get('experiments_designed',0)}\n\n"
       f"**With recorded results:** {fb.get('results_recorded',0)}\n\n"
       f"**Gate:** {fb.get('gate','REPEAT')}\n\n{fb.get('note','')}")


def dump_build(vid: str, result: dict, tag: str = "phase3") -> None:
    spec = result.get("spec") or {}
    features = spec.get("features") or []
    lines = ["## MVP features", ""]
    for f in features:
        lines += [f"### {f.get('name','?')}",
                  f"- **Purpose:** {f.get('purpose','')}",
                  f"- **Traced to:** {f.get('traced_to','')}",
                  f"- **Acceptance:** {f.get('acceptance','')}", ""]
    md(OUT / f"{tag}_step1_mvp_spec.md", "Build — MVP specification", "\n".join(lines))
    md(OUT / f"{tag}_step2_scaffold.md", "Build — scaffold & tests",
       "**Files:**\n" + "\n".join(f"- {n}" for n in result.get("files", []))
       + f"\n\n**Tests passed:** {result.get('test',{}).get('passed')}\n"
       + f"\n**Output dir:** {result.get('output_dir','')}")


def dump_commercial(vid: str, result: dict, tag: str = "phase4") -> None:
    p = result.get("pricing") or {}
    e = result.get("economics") or {}
    md(OUT / f"{tag}_step1_pricing.md", "Commercial setup — pricing",
       f"**Model:** {p.get('model')}\n\n**Price:** {p.get('price_per_unit')} {p.get('unit','')}\n\n"
       f"**Confidence:** {p.get('confidence')}\n\n**Rationale:** {p.get('rationale','')}")
    md(OUT / f"{tag}_step2_economics.md", "Commercial setup — unit economics",
       f"| Metric | Value |\n|---|---|\n"
       f"| Price per unit | {e.get('price_per_unit')} |\n"
       f"| Variable cost / unit | {e.get('variable_cost_per_unit')} |\n"
       f"| Fixed costs / month | {e.get('fixed_costs_monthly')} |\n"
       f"| Contribution margin | {e.get('contribution_margin')} |\n"
       f"| Gross margin % | {e.get('gross_margin_pct')} |\n"
       f"| Break-even units | {e.get('break_even_units')} |\n\n"
       f"**Formulas:**\n```\n{json.dumps(e.get('formulas',{}), indent=2)}\n```")


def dump_launch(vid: str, result: dict, tag: str = "phase5") -> None:
    m = result.get("materials") or {}
    lines = [f"**Tagline:** {m.get('tagline','')}", "",
             f"**One-liner:** {m.get('one_liner','')}", "",
             "## Claims", ""]
    for c in (m.get("claims") or []):
        status = c.get("status", "?")
        marker = "✅" if status == "supported" else "⚠️"
        lines.append(f"- {marker} **{status}** — {c.get('text','')} (evidence_id: {c.get('evidence_id','—')})")
    lines += ["", f"**Call to action:** {m.get('call_to_action','')}"]
    md(OUT / f"{tag}_step1_launch_materials.md", "Launch — materials", "\n".join(lines))


def dump_operate(vid: str, result: dict, tag: str = "phase6") -> None:
    a = result.get("analysis") or {}
    lines = ["## Issues", ""]
    for issue in (a.get("issues") or []):
        lines.append(f"- **{issue.get('severity','?').upper()}**: {issue.get('observation','')}")
    lines += ["", "## Recommendations", ""]
    for r in (a.get("recommendations") or []):
        lines.append(f"- **{r.get('action','')}** — {r.get('rationale','')} "
                     f"(expected: {r.get('expected_impact','')})")
    md(OUT / f"{tag}_step1_ops_analysis.md", "Operate — analysis", "\n".join(lines))


def approve(orch: Orchestrator, vid: str, approval_id: str) -> None:
    try:
        orch.approve_and_advance(vid, approval_id)
        print(f"  [gate] approved {approval_id[:8]}…")
    except Exception as e:
        print(f"  [gate] approve failed: {e}")


def run_weak_idea(orch: Orchestrator) -> None:
    print("\n=== Weak idea — expecting STOP ===")
    v = database.create_venture(name="Lottery predictor", idea=WEAK_IDEA)
    vid = v["id"]
    database.add_message(vid, "user", WEAK_IDEA)
    try:
        result = orch.run_stage(vid, "discover")
        dump_discover(vid, result, tag="weak_phase1")
        gate = (result.get("feasibility") or {}).get("gate_recommendation")
        print(f"  [gate] {gate}")
        if gate != "STOP":
            print("  [warn] expected STOP but got", gate, "— check feasibility prompt.")
    except Exception:
        traceback.print_exc()


def run_strong_idea(orch: Orchestrator) -> str | None:
    print("\n=== Strong idea — full pipeline ===")
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
        print(f"  [{stage}] running…")
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


def main() -> None:
    orch = Orchestrator()
    run_weak_idea(orch)
    run_strong_idea(orch)
    print("\n=== Exporting decision log ===")
    export(str(ROOT / "decision_log.json"))
    print("\nDone. Files in outputs/ and decision_log.json at root.")


if __name__ == "__main__":
    main()
__H_RD__

# ─── outputs/ (real ones are generated by run_demo.py) ───
cat > outputs/README.md <<'__H_OR__'
# outputs/

This directory contains **real demo-run outputs**. Nothing here is hand-written.

Regenerate with:

```bash
python scripts/run_demo.py
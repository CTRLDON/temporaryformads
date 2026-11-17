"""Mind-map data — progressive by completed stage."""
from __future__ import annotations
from config import STAGE_LABELS, STAGES
from memory import database
from services import evidence_ledger

LEAF_MAX = 55
ASPECT_MAX = 24

def _cut(s, n):
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"

def build(vid):
    v = database.get_venture(vid)
    if not v:
        raise ValueError("unknown venture")
    stages = database.get_stages(vid)
    evidence = evidence_ledger.list_for(vid)
    brief = v.get("brief") or {}
    gate = v.get("gate", "pending")
    current = v.get("current_stage", "discover")
    completed = {s for s, d in stages.items() if d.get("status") == "completed"}

    def ev(terms):
        return [e for e in evidence
                if e["type"] in ("verified", "experimental", "founder")
                and any(t in e["claim"].lower() for t in terms)]

    actions = []
    if gate == "STOP":
        actions = ["Pause — feasibility check failed",
                   "Draft a pivot or different approach",
                   "Re-run Discover once you have a new thesis"]
    elif gate == "PIVOT":
        actions = ["Identify the adjacent opportunity",
                   "Re-draft the brief with the new direction",
                   "Re-run Discover on the pivot"]
    elif gate == "REPEAT":
        actions = ["Gather additional evidence",
                   "Confirm assumptions with customers",
                   "Re-run the current stage"]
    elif gate == "GO":
        actions = [f"Approve '{current.title()}' and advance"]
    else:
        actions = ["Run the current stage to generate next actions"]
    for q in (brief.get("open_questions") or [])[:2]:
        actions.append(f"Answer: {_cut(q, 55)}")
    for a in (brief.get("assumptions") or [])[:2]:
        actions.append(f"Validate: {_cut(a, 55)}")

    nodes = [{"data": {"id": "center", "label": "Actionable\nSteps",
                       "type": "center", "items": actions}}]
    edges = []

    def add(label, children):
        idx = sum(1 for n in nodes if n["data"]["type"] == "aspect")
        nid = f"a{idx}"
        nodes.append({"data": {"id": nid, "label": _cut(label, ASPECT_MAX),
                              "type": "aspect"}})
        edges.append({"data": {"source": "center", "target": nid}})
        for j, child in enumerate(children):
            if not child:
                continue
            cid = f"{nid}c{j}"
            nodes.append({"data": {"id": cid, "label": _cut(str(child), LEAF_MAX),
                                  "type": "leaf"}})
            edges.append({"data": {"source": nid, "target": cid}})

    add("Concept", [brief.get("concept") or "Not yet defined"])
    add("Audience", [brief.get("target_audience") or "Not yet defined"])
    add("Model", [brief.get("business_model") or "Not yet defined"])

    if "discover" in completed:
        add("Market", [e["claim"] for e in ev(("market", "size", "growth", "demand"))][:3]
            or ["No verified findings"])
        add("Competitors", [e["claim"] for e in ev(("competit", "alternative", "rival"))][:3]
            or ["Not verified"])

    if "validate" in completed:
        exps = [e for e in evidence if e.get("stage") == "validate"
                and "Experiment:" in e["claim"]]
        add("Experiments", [e["claim"] for e in exps][:3] or ["No experiments"])
        add("Assumptions", [a for a in (brief.get("assumptions") or [])][:3]
            or ["No assumptions"])

    if "build" in completed:
        build_ev = [e for e in evidence if e.get("stage") == "build"]
        add("MVP", [e["claim"] for e in build_ev if "Feature:" in e["claim"]][:4]
            or ["No features"])
        add("Files", [e["claim"] for e in build_ev if "file" in e["claim"].lower()][:4]
            or ["No files"])

    if "commercial" in completed:
        comm = [e for e in evidence if e.get("stage") == "commercial"]
        add("Pricing", [e["claim"] for e in comm if "pric" in e["claim"].lower()][:2]
            or ["No pricing"])
        add("Economics", [e["claim"] for e in comm
                         if "margin" in e["claim"].lower()
                         or "break-even" in e["claim"].lower()][:3]
            or ["No economics"])

    if "launch" in completed:
        launch = [e for e in evidence if e.get("stage") == "launch"]
        add("Marketing", [e["claim"] for e in launch
                         if "claim" in e["claim"].lower()][:3]
            or ["No marketing"])

    if "operate" in completed:
        ops = [e for e in evidence if e.get("stage") == "operate"]
        add("Recommendations", [e["claim"] for e in ops
                               if "recommend" in e["claim"].lower()][:3]
            or ["No recommendations"])

    for stage in STAGES:
        if stage in completed:
            continue
        label = STAGE_LABELS[stage]
        if stage == current:
            add(f"{label} (now)", ["Run this stage to unlock"])
        else:
            add(f"{label} (locked)", ["Complete earlier stages first"])

    return {"nodes": nodes, "edges": edges, "stages_completed": sorted(completed)}

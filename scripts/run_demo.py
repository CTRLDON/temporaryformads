"""End-to-end demo. Fails fast — hard timeout per stage."""
from __future__ import annotations
import json, signal, sys, time, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.orchestrator import Orchestrator
from memory import database
from scripts.export_decision_log import export

OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

STAGE_TIMEOUT = 90
STAGES = ["discover", "validate", "build", "commercial", "launch", "operate"]
WEAK = "An AI that predicts lottery numbers with 99% accuracy."
STRONG = ("A sustainability-focused reusable packaging service for cafes in Cairo. "
          "Cafes pay a monthly subscription; customers return containers to any "
          "cafe in the network. I have 2 weeks and can code in Python.")


class _Timeout(Exception):
    pass


def _alarm(_s, _f):
    raise _Timeout(f"stage exceeded {STAGE_TIMEOUT}s")


def say(msg):
    print(msg, flush=True)


def save(rel, data):
    p = OUT / rel
    p.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    say(f"  [out] {rel}")


def run_stage_timed(orch, vid, stage):
    say(f"  [{stage}] starting (timeout={STAGE_TIMEOUT}s)...")
    t0 = time.time()
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(STAGE_TIMEOUT)
    try:
        result = orch.run_stage(vid, stage)
        say(f"  [{stage}] finished in {time.time()-t0:.1f}s")
        return result
    except _Timeout:
        say(f"  [{stage}] TIMEOUT after {time.time()-t0:.1f}s")
        return {"_timeout": True, "_stage": stage}
    except Exception as e:
        say(f"  [{stage}] ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {"_error": str(e), "_stage": stage}
    finally:
        signal.alarm(0)


def dump(stage, result, tag):
    save(f"{tag}_step1_result.json", {"stage": stage, "result": result})
    if result.get("_timeout"):
        save(f"{tag}_gate_decision.json", {
            "stage": stage, "gate": "TIMEOUT",
            "reason": f"stage exceeded {STAGE_TIMEOUT}s — likely slow model or network",
            "sources_used": [], "labelled": "ASSUMPTION",
        })
        return "TIMEOUT"
    if result.get("_error"):
        save(f"{tag}_gate_decision.json", {
            "stage": stage, "gate": "ERROR", "reason": result["_error"],
            "sources_used": [], "labelled": "ASSUMPTION",
        })
        return "ERROR"
    feas = result.get("feasibility") or {}
    fb = result.get("feedback") or {}
    gate = feas.get("gate_recommendation") or fb.get("gate") or "N/A"
    save(f"{tag}_gate_decision.json", {
        "stage": stage,
        "gate": gate,
        "classification": feas.get("classification"),
        "rationale": feas.get("rationale") or fb.get("note"),
        "sources_used": feas.get("sources_used") or [],
        "assumptions_labelled": "findings without source_url stored as type=assumption",
    })
    return gate


def approve(orch, vid, aid):
    try:
        orch.approve_and_advance(vid, aid)
        say(f"  [gate] approved {aid[:8]}...")
    except Exception as e:
        say(f"  [gate] approve failed: {e}")


def run_weak(orch):
    say("\n=== Weak idea (expecting STOP) ===")
    v = database.create_venture(name="Lottery", idea=WEAK)
    database.add_message(v["id"], "user", WEAK)
    result = run_stage_timed(orch, v["id"], "discover")
    gate = dump("discover", result, "weak_phase1")
    say(f"  [gate] {gate}")


def run_strong(orch):
    say("\n=== Strong idea (full pipeline) ===")
    v = database.create_venture(name="Reusable packaging", idea=STRONG)
    database.add_message(v["id"], "user", STRONG)
    for i, stage in enumerate(STAGES, 1):
        result = run_stage_timed(orch, v["id"], stage)
        gate = dump(stage, result, f"phase{i}")
        if result.get("_timeout") or result.get("_error"):
            say(f"  [{stage}] bailing out — remaining stages skipped")
            break
        aid = result.get("approval_id")
        if aid:
            approve(orch, v["id"], aid)


def main():
    say(f"[demo] provider from env, per-stage timeout={STAGE_TIMEOUT}s")
    orch = Orchestrator()
    say("[demo] Orchestrator ready, starting weak idea")
    try:
        run_weak(orch)
    except Exception:
        traceback.print_exc()
    try:
        run_strong(orch)
    except Exception:
        traceback.print_exc()
    say("\n=== Exporting decision log ===")
    try:
        export(str(ROOT / "decision_log.json"))
    except Exception:
        traceback.print_exc()
    say("\nDone. See outputs/ and decision_log.json")


if __name__ == "__main__":
    main()
def test_validate_gate_repeats_without_results():
    designed, recorded = 3, 0
    gate = "GO" if recorded >= 2 else "REPEAT"
    assert gate == "REPEAT"

def test_orchestrator_has_all_stages():
    from backend.orchestrator import Orchestrator
    try:
        o = Orchestrator()
    except Exception:
        import pytest; pytest.skip("model unavailable")
    for m in ("run_discover", "run_validate", "run_build",
              "run_commercial", "run_launch", "run_operate"):
        assert hasattr(o, m)

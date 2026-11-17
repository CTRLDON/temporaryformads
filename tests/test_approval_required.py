def test_approval_row_created_on_gate():
    from memory import database
    from backend import approval_manager
    v = database.create_venture(name="Approval test", idea="test")
    aid = approval_manager.request(v["id"], action="discover_gate",
                                   payload={"recommendation": "GO"})
    assert any(a["id"] == aid for a in approval_manager.list_pending(v["id"]))

def test_require_approved_raises():
    from memory import database
    from backend.approval_manager import require_approved, ApprovalRequired
    v = database.create_venture(name="Approval test 2", idea="test")
    try:
        require_approved(v["id"], "discover_gate")
        assert False
    except ApprovalRequired:
        pass

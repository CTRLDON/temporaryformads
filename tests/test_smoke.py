def test_import_app():
    from backend.app import app
    assert app.title == "VentureOS"

def test_config_endpoint():
    from fastapi.testclient import TestClient
    from backend.app import app
    with TestClient(app) as c:
        r = c.get("/api/config")
        assert r.status_code == 200
        assert len(r.json()["stages"]) == 6

def test_stages_defined():
    from config import STAGES, STAGE_LABELS
    assert STAGES == ["discover", "validate", "build", "commercial", "launch", "operate"]
    assert all(s in STAGE_LABELS for s in STAGES)

def test_database_initialises():
    from memory import database
    v = database.create_venture(name="Test", idea="A test idea")
    assert v["id"]
    assert len(database.get_stages(v["id"])) == 6

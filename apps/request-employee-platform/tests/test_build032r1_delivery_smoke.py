from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_build032r1_runtime_alive():
    r = client.get("/api/system/runtime")
    assert r.status_code == 200
    assert "version" in r.json()


def test_build032r1_bank_router_available():
    r = client.get("/api/bank/reconciliation/settings")
    assert r.status_code in (200, 404)

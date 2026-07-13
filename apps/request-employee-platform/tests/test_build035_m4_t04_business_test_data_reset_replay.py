
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _unique_month():
    value = uuid4().int
    year = 5000 + (value % 4000)
    month = 1 + ((value // 4000) % 12)
    return f"{year:04d}-{month:02d}"


def test_replay_creates_isolated_batch_and_import_jobs():
    month = _unique_month()

    replay = client.post("/api/tlc-business-test/replay", json={
        "business_month": month,
        "operator": "tester",
        "scenario_name": "STANDARD",
    })
    assert replay.status_code == 200, replay.text
    body = replay.json()
    assert body["business_month"] == month
    assert body["created_count"] >= 1

    home = client.get(
        "/api/tlc-business-operations-home",
        params={"business_month": month},
    )
    assert home.status_code == 200
    assert home.json()["batch_count"] == 1
    batches = client.get("/api/tlc-batches", params={"business_month": month})
    assert batches.status_code == 200
    assert batches.json()[0].get("sequence_no", 1) >= 1


def test_reset_requires_exact_confirmation_and_removes_month():
    month = _unique_month()

    replay = client.post("/api/tlc-business-test/replay", json={
        "business_month": month,
        "operator": "tester",
    })
    assert replay.status_code == 200

    invalid = client.post("/api/tlc-business-test/reset", json={
        "business_month": month,
        "operator": "tester",
        "confirmation": "RESET",
    })
    assert invalid.status_code == 400

    reset = client.post("/api/tlc-business-test/reset", json={
        "business_month": month,
        "operator": "tester",
        "confirmation": f"RESET {month}",
    })
    assert reset.status_code == 200, reset.text
    assert reset.json()["deleted_count"] >= 1

    home = client.get(
        "/api/tlc-business-operations-home",
        params={"business_month": month},
    )
    assert home.status_code == 200
    assert home.json()["batch_count"] == 0


def test_replay_page_available_and_connected():
    response = client.get("/business-test-replay")
    assert response.status_code == 200
    html = response.text
    assert "Business Test Data Reset & Replay" in html
    assert "/api/tlc-business-test/reset" in html
    assert "/api/tlc-business-test/replay" in html
    assert 'href="/guided-monthly-workflow"' in html
    assert 'href="/end-to-end-readiness"' in html

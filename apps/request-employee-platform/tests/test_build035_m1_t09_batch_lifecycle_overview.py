from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def make_batch():
    response = client.post("/api/tlc-batches", json={
        "business_month": "2027-06",
        "title": f"Lifecycle {uuid4().hex[:8]}",
        "created_by": "tester",
    })
    assert response.status_code == 200, response.text
    return response.json()

def test_overview_and_timeline():
    batch = make_batch()
    overview = client.get(
        f"/api/tlc-batches/{batch['id']}/lifecycle-overview"
    )
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["batch"]["id"] == batch["id"]
    assert body["total_step_count"] == 8
    assert len(body["checks"]) == 8

    timeline = client.get(
        f"/api/tlc-batches/{batch['id']}/lifecycle-timeline"
    )
    assert timeline.status_code == 200
    assert any(
        item["event_type"] == "BATCH_CREATED"
        for item in timeline.json()
    )

def test_history_tab_connected():
    html = client.get("/batch-center").text
    assert "/lifecycle-overview" in html
    assert "/lifecycle-timeline" in html
    assert "Batch Lifecycle Overview" in html
    assert "Completion" in html

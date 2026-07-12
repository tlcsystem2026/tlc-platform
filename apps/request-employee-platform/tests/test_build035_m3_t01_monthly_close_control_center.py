
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _batch(month: str, title: str):
    response = client.post("/api/tlc-batches", json={
        "business_month": month,
        "title": title,
        "created_by": "tester",
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_month_without_batch_is_not_ready():
    month = "2099-01"
    response = client.get(f"/api/tlc-monthly-close/{month}")
    assert response.status_code == 200
    body = response.json()
    assert body["batch_count"] == 0
    assert body["close_ready"] is False
    assert body["blockers"]


def test_new_batch_appears_as_unfinished_blocker():
    month = "2099-02"
    batch = _batch(month, f"Monthly Close {uuid4().hex[:8]}")

    response = client.get(f"/api/tlc-monthly-close/{month}")
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["batch_count"] == 1
    assert body["unfinished_batch_count"] == 1
    assert body["close_ready"] is False
    assert body["batch_summaries"][0]["batch"]["id"] == batch["id"]
    assert any(
        "batch status=" in item
        for item in body["batch_summaries"][0]["blockers"]
    )


def test_finished_batch_without_errors_is_close_ready():
    month = "2099-03"
    batch = _batch(month, f"Finished {uuid4().hex[:8]}")

    for status in [
        "IMPORTING",
        "COMPARE",
        "READY_REVIEW",
        "REVIEWING",
        "LEDGER_POSTED",
        "BANK_IMPORTED",
        "RECONCILING",
        "FINISHED",
    ]:
        response = client.post(
            f"/api/tlc-batches/{batch['id']}/transition",
            json={"new_status": status, "operator": "tester"},
        )
        assert response.status_code == 200, response.text

    response = client.get(f"/api/tlc-monthly-close/{month}")
    assert response.status_code == 200
    body = response.json()
    assert body["finished_batch_count"] == 1
    assert body["close_ready"] is True
    assert body["blockers"] == []


def test_monthly_close_page_available():
    response = client.get("/monthly-close-center")
    assert response.status_code == 200
    html = response.text
    assert "Monthly Close Control Center" in html
    assert "/api/tlc-monthly-close/" in html
    assert "/batch-center" in html
    assert "/import-center" in html


from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _unique_month():
    value = uuid4().int
    year = 3000 + (value % 6000)
    month = 1 + ((value // 6000) % 12)
    return f"{year:04d}-{month:02d}"


def _batch(month: str):
    response = client.post("/api/tlc-batches", json={
        "business_month": month,
        "title": f"Guided Workflow {uuid4().hex[:8]}",
        "created_by": "tester",
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_month_recommends_batch_setup():
    month = _unique_month()

    response = client.get(
        "/api/tlc-guided-monthly-workflow",
        params={"business_month": month},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["completed_step_count"] == 0
    assert body["next_step_code"] == "BATCH_SETUP"
    assert body["steps"][0]["recommended"] is True


def test_created_batch_completes_first_step():
    month = _unique_month()
    _batch(month)

    response = client.get(
        "/api/tlc-guided-monthly-workflow",
        params={"business_month": month},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["steps"][0]["code"] == "BATCH_SETUP"
    assert body["steps"][0]["status"] == "DONE"
    assert body["next_step_code"] == "REQUEST_IMPORT"


def test_guided_workflow_page_available_and_connected():
    response = client.get("/guided-monthly-workflow")
    assert response.status_code == 200
    html = response.text
    assert "Guided Monthly Operation Workflow" in html
    assert "/api/tlc-guided-monthly-workflow" in html
    assert 'href="/business-operations-home"' in html
    assert 'href="/operational-exception-dashboard"' in html
    assert 'href="/batch-center"' not in html  # step links are dynamically rendered

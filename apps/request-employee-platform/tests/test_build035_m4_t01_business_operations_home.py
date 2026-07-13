
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _unique_month():
    value = uuid4().int
    year = 2200 + (value % 7000)
    month = 1 + ((value // 7000) % 12)
    return f"{year:04d}-{month:02d}"


def _batch(month: str):
    response = client.post("/api/tlc-batches", json={
        "business_month": month,
        "title": f"Operations Home {uuid4().hex[:8]}",
        "created_by": "tester",
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_home_reports_unfinished_batch_alert():
    month = _unique_month()
    batch = _batch(month)

    response = client.get(
        "/api/tlc-business-operations-home",
        params={"business_month": month},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["business_month"] == month
    assert body["batch_count"] == 1
    assert body["unfinished_batch_count"] == 1
    assert any(
        alert["code"] == "BATCH_NOT_FINISHED"
        for alert in body["alerts"]
    )
    assert any(
        item["path"] == "/batch-center"
        for item in body["navigation"]
    )


def test_home_reports_import_error():
    month = _unique_month()
    batch = _batch(month)

    created = client.post("/api/tlc-import-jobs", json={
        "batch_id": batch["id"],
        "import_type": "BANK_CSV",
        "source_name": "bank.csv",
        "source_reference": f"SRC-{uuid4().hex}",
        "created_by": "tester",
    }).json()["job"]

    client.put(
        f"/api/tlc-import-jobs/{created['id']}",
        json={"status": "PROCESSING", "operator": "tester"},
    )
    failed = client.put(
        f"/api/tlc-import-jobs/{created['id']}",
        json={
            "status": "ERROR",
            "operator": "tester",
            "error_count": 1,
        },
    )
    assert failed.status_code == 200

    response = client.get(
        "/api/tlc-business-operations-home",
        params={"business_month": month},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["import_error_job_count"] == 1
    assert any(
        alert["code"] == "IMPORT_JOB_ERROR"
        for alert in body["alerts"]
    )


def test_home_page_available_and_connected():
    response = client.get("/business-operations-home")
    assert response.status_code == 200
    html = response.text
    assert "Business Operations Home" in html
    assert "/api/tlc-business-operations-home" in html
    assert 'href="/batch-center"' in html
    assert 'href="/import-center"' in html
    assert 'href="/monthly-close-center"' in html
    assert 'href="/operational-exception-dashboard"' in html

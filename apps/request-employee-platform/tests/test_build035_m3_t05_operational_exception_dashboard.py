
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _batch(month: str):
    response = client.post("/api/tlc-batches", json={
        "business_month": month,
        "title": f"Exception {uuid4().hex[:8]}",
        "created_by": "tester",
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_new_batch_appears_as_low_exception():
    month = "2100-02"
    batch = _batch(month)

    response = client.get(
        "/api/tlc-operational-exceptions",
        params={"business_month": month},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["exception_count"] >= 1
    assert any(
        item["category"] == "BATCH_NOT_FINISHED"
        and item["batch_id"] == batch["id"]
        for item in body["exceptions"]
    )


def test_import_job_error_appears_as_high_exception():
    month = "2100-03"
    batch = _batch(month)

    created = client.post("/api/tlc-import-jobs", json={
        "batch_id": batch["id"],
        "import_type": "BANK_CSV",
        "source_name": "bank.csv",
        "source_reference": f"SRC-{uuid4().hex}",
        "created_by": "tester",
    }).json()["job"]

    processing = client.put(
        f"/api/tlc-import-jobs/{created['id']}",
        json={"status": "PROCESSING", "operator": "tester"},
    )
    assert processing.status_code == 200

    failed = client.put(
        f"/api/tlc-import-jobs/{created['id']}",
        json={
            "status": "ERROR",
            "operator": "tester",
            "error_count": 1,
            "message": "Import failed",
        },
    )
    assert failed.status_code == 200

    response = client.get(
        "/api/tlc-operational-exceptions",
        params={"business_month": month},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["high_count"] >= 1
    assert any(
        item["category"] == "IMPORT_JOB_ERROR"
        and item["reference_id"] == created["id"]
        for item in body["exceptions"]
    )


def test_pending_authorization_appears_as_medium_exception():
    month = "2100-04"
    _batch(month)

    requested = client.post(
        "/api/tlc-monthly-close/authorizations",
        json={
            "business_month": month,
            "action": "CLOSE",
            "requested_by": "requester",
            "reason": "Waiting for approval",
        },
    )
    assert requested.status_code == 200, requested.text

    response = client.get(
        "/api/tlc-operational-exceptions",
        params={"business_month": month},
    )
    assert response.status_code == 200

    assert any(
        item["category"] == "AUTHORIZATION_PENDING"
        for item in response.json()["exceptions"]
    )


def test_dashboard_page_available():
    response = client.get("/operational-exception-dashboard")
    assert response.status_code == 200
    html = response.text
    assert "Operational Exception Dashboard" in html
    assert "/api/tlc-operational-exceptions" in html
    assert "/monthly-close-center" in html
    assert "/import-center" in html
    assert "/batch-center" in html


def test_compare_error_schema_is_tolerated():
    month = "2100-05"
    _batch(month)
    response = client.get(
        "/api/tlc-operational-exceptions",
        params={"business_month": month},
    )
    assert response.status_code == 200, response.text
    assert "exceptions" in response.json()

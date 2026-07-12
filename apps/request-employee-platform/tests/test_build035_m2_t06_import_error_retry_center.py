
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _batch():
    response = client.post("/api/tlc-batches", json={
        "business_month": "2027-12",
        "title": f"Import Retry {uuid4().hex[:8]}",
        "created_by": "tester",
    })
    assert response.status_code == 200, response.text
    return response.json()


def _error_job(batch_id: str):
    created = client.post("/api/tlc-import-jobs", json={
        "batch_id": batch_id,
        "import_type": "BANK_CSV",
        "source_name": "bank.csv",
        "source_reference": f"SRC-{uuid4().hex}",
        "created_by": "tester",
    })
    assert created.status_code == 200, created.text
    job = created.json()["job"]

    processing = client.put(
        f"/api/tlc-import-jobs/{job['id']}",
        json={"status": "PROCESSING", "operator": "tester"},
    )
    assert processing.status_code == 200

    failed = client.put(
        f"/api/tlc-import-jobs/{job['id']}",
        json={
            "status": "ERROR",
            "operator": "tester",
            "record_count": 5,
            "success_count": 4,
            "error_count": 1,
        },
    )
    assert failed.status_code == 200
    return failed.json()


def test_error_resolution_and_retry_success():
    batch = _batch()
    job = _error_job(batch["id"])

    error = client.post("/api/tlc-import-operations/errors", json={
        "import_job_id": job["id"],
        "error_code": "INVALID_AMOUNT",
        "record_reference": "ROW-5",
        "field_name": "amount",
        "source_value": "ABC",
        "message": "Amount is invalid",
    })
    assert error.status_code == 200, error.text

    resolved = client.put(
        f"/api/tlc-import-operations/errors/{error.json()['id']}",
        json={
            "status": "RESOLVED",
            "operator": "tester",
            "resolution_note": "Source corrected",
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"

    retry = client.post("/api/tlc-import-operations/retries", json={
        "import_job_id": job["id"],
        "requested_by": "tester",
    })
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "PROCESSING"

    completed = client.put(
        f"/api/tlc-import-operations/retries/{retry.json()['id']}/complete",
        json={
            "status": "SUCCESS",
            "operator": "tester",
            "record_count": 5,
            "success_count": 5,
            "error_count": 0,
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "SUCCESS"

    jobs = client.get(
        "/api/tlc-import-jobs",
        params={"batch_id": batch["id"]},
    )
    assert jobs.json()[0]["status"] == "SUCCESS"


def test_retry_requires_error_or_staged_job():
    batch = _batch()
    created = client.post("/api/tlc-import-jobs", json={
        "batch_id": batch["id"],
        "import_type": "REQUEST_EXCEL",
        "source_name": "request.xlsx",
        "source_reference": f"SRC-{uuid4().hex}",
        "created_by": "tester",
    }).json()["job"]

    response = client.post("/api/tlc-import-operations/retries", json={
        "import_job_id": created["id"],
        "requested_by": "tester",
    })
    assert response.status_code == 400
    assert "Only ERROR or STAGED" in response.json()["detail"]


def test_summary_and_import_center_connection():
    batch = _batch()
    job = _error_job(batch["id"])
    client.post("/api/tlc-import-operations/errors", json={
        "import_job_id": job["id"],
        "message": "Test error",
    })
    client.post("/api/tlc-import-operations/retries", json={
        "import_job_id": job["id"],
        "requested_by": "tester",
    })

    summary = client.get(
        "/api/tlc-import-operations/summary",
        params={"batch_id": batch["id"]},
    )
    assert summary.status_code == 200
    body = summary.json()
    assert body["error_count"] == 1
    assert body["open_error_count"] == 1
    assert body["retry_count"] == 1

    html = client.get("/import-center").text
    assert "/api/tlc-import-operations/errors" in html
    assert "/api/tlc-import-operations/retries" in html
    assert "Import Error / Retry Center" in html

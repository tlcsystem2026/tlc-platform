from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _batch():
    response = client.post("/api/tlc-batches", json={
        "business_month": "2027-07",
        "title": f"Import Center {uuid4().hex[:8]}",
        "created_by": "tester",
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_import_job_create_update_and_summary():
    batch = _batch()
    source_reference = f"FILE-{uuid4().hex}"

    created = client.post("/api/tlc-import-jobs", json={
        "batch_id": batch["id"],
        "import_type": "BANK_CSV",
        "source_name": "bank.csv",
        "source_reference": source_reference,
        "created_by": "tester",
    })
    assert created.status_code == 200, created.text
    job = created.json()["job"]
    assert job["status"] == "NEW"

    processing = client.put(
        f"/api/tlc-import-jobs/{job['id']}",
        json={
            "status": "PROCESSING",
            "operator": "tester",
            "record_count": 10,
        },
    )
    assert processing.status_code == 200, processing.text
    assert processing.json()["status"] == "PROCESSING"

    success = client.put(
        f"/api/tlc-import-jobs/{job['id']}",
        json={
            "status": "SUCCESS",
            "operator": "tester",
            "record_count": 10,
            "success_count": 8,
            "error_count": 1,
            "duplicate_count": 1,
        },
    )
    assert success.status_code == 200, success.text
    assert success.json()["success_count"] == 8

    summary = client.get(
        "/api/tlc-import-jobs-summary",
        params={"batch_id": batch["id"]},
    )
    assert summary.status_code == 200
    body = summary.json()
    assert body["job_count"] == 1
    assert body["success_count"] == 1
    assert body["imported_record_count"] == 8
    assert body["error_record_count"] == 1
    assert body["duplicate_record_count"] == 1


def test_import_job_is_idempotent():
    batch = _batch()
    payload = {
        "batch_id": batch["id"],
        "import_type": "REQUEST_EXCEL",
        "source_name": "request.xlsx",
        "source_reference": f"FILE-{uuid4().hex}",
        "created_by": "tester",
    }

    first = client.post("/api/tlc-import-jobs", json=payload)
    second = client.post("/api/tlc-import-jobs", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "exists"
    assert first.json()["job"]["id"] == second.json()["job"]["id"]


def test_invalid_import_transition_is_rejected():
    batch = _batch()
    created = client.post("/api/tlc-import-jobs", json={
        "batch_id": batch["id"],
        "import_type": "REQUEST_PDF",
        "source_name": "request.pdf",
        "source_reference": f"FILE-{uuid4().hex}",
        "created_by": "tester",
    }).json()["job"]

    response = client.put(
        f"/api/tlc-import-jobs/{created['id']}",
        json={"status": "SUCCESS", "operator": "tester"},
    )
    assert response.status_code == 400
    assert "Invalid import status transition" in response.json()["detail"]


def test_import_center_page_available():
    response = client.get("/import-center")
    assert response.status_code == 200
    html = response.text
    assert "Unified Import Center" in html
    assert "/api/tlc-import-jobs" in html
    assert "/api/tlc-import-jobs-summary" in html
    assert "/batch-center" in html
    assert "/bank-import" in html

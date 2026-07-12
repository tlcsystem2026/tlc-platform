from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_batch_center_page_available():
    response = client.get("/batch-center")
    assert response.status_code == 200
    html = response.text
    assert "Batch Center" in html
    assert "/api/tlc-batches" in html
    assert "Request Import" in html
    assert "Compare" in html
    assert "Review" in html
    assert "Sales Ledger" in html
    assert "Bank Import" in html
    assert "Reconciliation" in html
    assert "History" in html


def test_batch_number_generation_and_sequence():
    suffix = uuid4().hex[:8]
    month = "2026-07"

    first = client.post("/api/tlc-batches", json={
        "business_month": month,
        "title": f"Acceptance Batch A {suffix}",
        "created_by": "tester",
    })
    second = client.post("/api/tlc-batches", json={
        "business_month": "202607",
        "title": f"Acceptance Batch B {suffix}",
        "created_by": "tester",
    })

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["batch_no"].startswith("202607-")
    assert second.json()["batch_no"].startswith("202607-")
    assert second.json()["sequence_no"] == first.json()["sequence_no"] + 1


def test_batch_update_transition_and_timeline():
    suffix = uuid4().hex[:8]
    created = client.post("/api/tlc-batches", json={
        "business_month": "2026-08",
        "title": f"Transition Batch {suffix}",
        "created_by": "tester",
        "owner": "owner-a",
    })
    assert created.status_code == 200, created.text
    batch = created.json()

    updated = client.put(f"/api/tlc-batches/{batch['id']}", json={
        "title": f"Updated Transition Batch {suffix}",
        "owner": "owner-b",
        "source_folder": r"Y:\Requests\202608",
        "note": "updated",
        "operator": "tester",
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["owner"] == "owner-b"

    importing = client.post(
        f"/api/tlc-batches/{batch['id']}/transition",
        json={
            "new_status": "IMPORTING",
            "operator": "tester",
            "message": "Import started",
        },
    )
    assert importing.status_code == 200, importing.text
    assert importing.json()["status"] == "IMPORTING"

    compare = client.post(
        f"/api/tlc-batches/{batch['id']}/transition",
        json={
            "new_status": "COMPARE",
            "operator": "tester",
        },
    )
    assert compare.status_code == 200, compare.text
    assert compare.json()["status"] == "COMPARE"

    timeline = client.get(f"/api/tlc-batches/{batch['id']}/timeline")
    assert timeline.status_code == 200
    event_types = {row["event_type"] for row in timeline.json()}
    assert {"BATCH_CREATED", "BATCH_UPDATED", "STATUS_CHANGED"} <= event_types


def test_invalid_status_transition_is_rejected():
    created = client.post("/api/tlc-batches", json={
        "business_month": "2026-09",
        "title": f"Invalid Transition {uuid4().hex[:8]}",
        "created_by": "tester",
    })
    assert created.status_code == 200
    batch = created.json()

    response = client.post(
        f"/api/tlc-batches/{batch['id']}/transition",
        json={
            "new_status": "LEDGER_POSTED",
            "operator": "tester",
        },
    )
    assert response.status_code == 400
    assert "Invalid batch status transition" in response.json()["detail"]


def test_finished_batch_cannot_be_edited():
    created = client.post("/api/tlc-batches", json={
        "business_month": "2026-10",
        "title": f"Finish Batch {uuid4().hex[:8]}",
        "created_by": "tester",
    })
    batch = created.json()

    finished = client.post(
        f"/api/tlc-batches/{batch['id']}/transition",
        json={
            "new_status": "FINISHED",
            "operator": "tester",
        },
    )
    assert finished.status_code == 200

    update = client.put(f"/api/tlc-batches/{batch['id']}", json={
        "title": "Should fail",
    })
    assert update.status_code == 400
    assert "Finished batch cannot be edited" in update.json()["detail"]

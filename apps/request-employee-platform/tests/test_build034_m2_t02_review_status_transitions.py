from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def _create_pending():
    no = f"REQ-M2T02-{uuid4().hex[:12]}"
    payload = {
        "matched": True,
        "request_no": no,
        "difference_count": 0,
        "sources": {"excel": no + ".xlsx", "pdf": no + ".pdf"},
        "request_document": {
            "request_no": no,
            "request_date": "2026-07-10",
            "customer_id": "CUST-REVIEW",
            "customer_name": "Review Customer",
            "currency": "JPY",
            "subtotal": "1000",
            "tax_amount": "100",
            "total_amount": "1100",
        },
    }
    response = client.post("/api/requests/pending-review", json=payload)
    assert response.status_code == 200
    return response.json()["record"]


def _resolve(action):
    record = _create_pending()
    response = client.post(
        f"/api/requests/pending-review/{record['id']}/resolve",
        json={"action": action, "reviewed_by": "reviewer001", "note": action},
    )
    assert response.status_code == 200
    return response.json()


def test_all_review_actions():
    assert _resolve("APPROVE")["new_status"] == "APPROVED"
    assert _resolve("REJECT")["new_status"] == "REJECTED"
    assert _resolve("CANCEL")["new_status"] == "CANCELLED"
    assert _resolve("MARK_DUPLICATE")["new_status"] == "DUPLICATE"


def test_finalized_record_cannot_be_resolved_twice():
    record = _create_pending()
    first = client.post(
        f"/api/requests/pending-review/{record['id']}/resolve",
        json={"action": "APPROVE", "reviewed_by": "reviewer001"},
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/requests/pending-review/{record['id']}/resolve",
        json={"action": "CANCEL", "reviewed_by": "reviewer002"},
    )
    assert second.status_code == 400
    assert "already finalized" in second.json()["detail"]


def test_unknown_record_returns_404():
    response = client.post(
        f"/api/requests/pending-review/{uuid4().hex}/resolve",
        json={"action": "APPROVE", "reviewed_by": "reviewer001"},
    )
    assert response.status_code == 404


def test_review_history_is_recorded():
    record = _create_pending()
    resolved = client.post(
        f"/api/requests/pending-review/{record['id']}/resolve",
        json={"action": "REJECT", "reviewed_by": "reviewer001", "note": "missing evidence"},
    )
    assert resolved.status_code == 200
    history = client.get(f"/api/requests/pending-review/{record['id']}/history")
    assert history.status_code == 200
    rows = history.json()
    assert len(rows) == 1
    assert rows[0]["old_status"] == "PENDING_REVIEW"
    assert rows[0]["new_status"] == "REJECTED"
    assert rows[0]["reviewed_by"] == "reviewer001"

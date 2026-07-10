from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app
client = TestClient(app)

def payload(no, matched=True):
    return {
        "matched": matched, "request_no": no, "difference_count": 0 if matched else 1,
        "sources": {"excel": no+".xlsx", "pdf": no+".pdf"},
        "request_document": {
            "request_no": no, "request_date": "2026-07-10", "customer_id": "CUST-034",
            "customer_name": "Build034 Customer", "currency": "JPY",
            "subtotal": "1000", "tax_amount": "100", "total_amount": "1100"
        }
    }

def test_matched_request_enters_pending_review_database():
    no = "REQ-M2T01-" + uuid4().hex[:12]
    r = client.post("/api/requests/pending-review", json=payload(no))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "created"
    assert body["record"]["status"] == "PENDING_REVIEW"
    rid = body["record"]["id"]
    detail = client.get(f"/api/requests/pending-review/{rid}")
    assert detail.status_code == 200
    assert detail.json()["request_no"] == no

def test_mismatch_request_is_rejected():
    no = "REQ-M2T01-ERR-" + uuid4().hex[:10]
    r = client.post("/api/requests/pending-review", json=payload(no, False))
    assert r.status_code == 400

def test_duplicate_request_is_idempotent():
    no = "REQ-M2T01-DUP-" + uuid4().hex[:10]
    a = client.post("/api/requests/pending-review", json=payload(no)).json()
    b = client.post("/api/requests/pending-review", json=payload(no)).json()
    assert a["status"] == "created"
    assert b["status"] == "exists"
    assert a["record"]["id"] == b["record"]["id"]

def test_list_pending_review_records():
    no = "REQ-M2T01-LIST-" + uuid4().hex[:10]
    assert client.post("/api/requests/pending-review", json=payload(no)).status_code == 200
    rows = client.get("/api/requests/pending-review", params={"status":"PENDING_REVIEW"}).json()
    assert any(row["request_no"] == no for row in rows)

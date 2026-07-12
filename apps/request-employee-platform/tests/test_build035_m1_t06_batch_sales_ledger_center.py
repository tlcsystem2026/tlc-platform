from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from src.main import app
from src.db.session import SessionLocal
from src.services.tlc_batch_compare_service import ensure_compare_table

client = TestClient(app)

def _reviewing_batch():
    batch = client.post("/api/tlc-batches", json={
        "business_month": "2027-03",
        "title": f"Sales Ledger Batch {uuid4().hex[:10]}",
        "created_by": "tester",
    }).json()

    for status in ["IMPORTING", "COMPARE", "READY_REVIEW"]:
        response = client.post(
            f"/api/tlc-batches/{batch['id']}/transition",
            json={"new_status": status, "operator": "tester"},
        )
        assert response.status_code == 200, response.text

    db = SessionLocal()
    try:
        ensure_compare_table(db)
        db.execute(text("""
            INSERT INTO tlc_batch_compare_result (
                id, batch_id, excel_file_id, pdf_file_id,
                request_no, matched, difference_count,
                result_json, status, compared_by, compared_at
            ) VALUES (
                :id, :batch_id, :excel_file_id, :pdf_file_id,
                :request_no, 1, 0, :result_json,
                'MATCHED', 'tester', :compared_at
            )
        """), {
            "id": uuid4().hex,
            "batch_id": batch["id"],
            "excel_file_id": uuid4().hex,
            "pdf_file_id": uuid4().hex,
            "request_no": f"REQ-{uuid4().hex[:8]}",
            "result_json": '{"matched": true, "difference_count": 0, "request_no": "REQ-TEST"}',
            "compared_at": datetime.now(timezone.utc).isoformat(),
        })
        db.commit()
    finally:
        db.close()

    linked = client.post(
        f"/api/tlc-batches/{batch['id']}/review/links",
        json={
            "pending_review_id": f"PR-{uuid4().hex[:10]}",
            "linked_by": "tester",
        },
    )
    assert linked.status_code == 200, linked.text
    return batch, linked.json()["review_link"]

def test_sales_ledger_link_moves_batch_to_ledger_posted():
    batch, review = _reviewing_batch()
    ledger_id = f"SL-{uuid4().hex[:10]}"
    response = client.post(
        f"/api/tlc-batches/{batch['id']}/sales-ledger/links",
        json={
            "review_link_id": review["id"],
            "sales_ledger_id": ledger_id,
            "posted_by": "tester",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "linked"
    assert client.get(f"/api/tlc-batches/{batch['id']}").json()["status"] == "LEDGER_POSTED"

def test_sales_ledger_link_is_idempotent():
    batch, review = _reviewing_batch()
    payload = {
        "review_link_id": review["id"],
        "sales_ledger_id": f"SL-{uuid4().hex[:10]}",
        "posted_by": "tester",
    }
    first = client.post(f"/api/tlc-batches/{batch['id']}/sales-ledger/links", json=payload)
    second = client.post(f"/api/tlc-batches/{batch['id']}/sales-ledger/links", json=payload)
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["status"] == "exists"
    assert first.json()["ledger_link"]["id"] == second.json()["ledger_link"]["id"]

def test_sales_ledger_summary_and_page_connection():
    batch, review = _reviewing_batch()
    client.post(
        f"/api/tlc-batches/{batch['id']}/sales-ledger/links",
        json={
            "review_link_id": review["id"],
            "sales_ledger_id": f"SL-{uuid4().hex[:10]}",
            "posted_by": "tester",
        },
    )
    summary = client.get(f"/api/tlc-batches/{batch['id']}/sales-ledger/summary")
    assert summary.status_code == 200
    assert summary.json()["ledger_count"] == 1
    html = client.get("/batch-center").text
    assert "/sales-ledger/links" in html
    assert "/sales-ledger/summary" in html
    assert "登记正式台账" in html
    assert 'name==="sales"' in html

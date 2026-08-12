import os
import tempfile
from pathlib import Path
from uuid import uuid4


TEST_DB = Path(tempfile.gettempdir()) / f"tlc_sales_ledger_admin_{uuid4().hex}.sqlite3"
os.environ["TLC_DATABASE_URL"] = "sqlite:///" + TEST_DB.as_posix()
os.environ["TLC_DOCUMENT_ROOT"] = str(Path(tempfile.gettempdir()) / "tlc_sales_ledger_admin_documents")
os.environ["TLC_SUPER_ADMIN_OPERATORS"] = "super-admin"

from fastapi.testclient import TestClient
from sqlalchemy import text

from src.db.session import SessionLocal
from src.main import app


client = TestClient(app)


def _posted_ledger(tag: str):
    token = uuid4().hex[:10]
    request_no = f"REQ-{tag}-{token}"
    payload = {
        "matched": True,
        "request_no": request_no,
        "difference_count": 0,
        "sources": {"excel": request_no + ".xlsx", "pdf": request_no + ".pdf"},
        "request_document": {
            "request_no": request_no,
            "request_date": "2026-08-03",
            "customer_id": f"CUST-{tag}-{token}",
            "customer_name": f"{tag} Customer",
            "currency": "JPY",
            "subtotal": "1000",
            "tax_amount": "100",
            "total_amount": "1100",
        },
    }
    pending = client.post("/api/requests/pending-review", json=payload)
    assert pending.status_code == 200, pending.text
    record_id = pending.json()["record"]["id"]
    approved = client.post(
        f"/api/requests/pending-review/{record_id}/resolve",
        json={"action": "APPROVE", "reviewed_by": "cleanup-test", "note": "test"},
    )
    assert approved.status_code == 200, approved.text
    posted = client.post(f"/api/sales-ledger/from-pending-review/{record_id}")
    assert posted.status_code == 200, posted.text
    return posted.json()["ledger"]


def test_super_admin_cleanup_requires_role_and_exact_confirmation():
    ledger = _posted_ledger("TEST")
    base = {
        "ledger_ids": [ledger["id"]],
        "operator": "super-admin",
        "reason": "remove automated test data",
        "confirmation": "DELETE TEST DATA",
    }
    denied = client.post(
        "/api/sales-ledger/admin/cleanup-test-data",
        json={**base, "role": "ADMIN"},
    )
    assert denied.status_code == 403
    deleted = client.post(
        "/api/sales-ledger/admin/cleanup-test-data",
        json={**base, "role": "SUPER_ADMIN"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] == 1
    assert client.get(f"/api/sales-ledger/{ledger['id']}").status_code == 404


def test_cleanup_reports_the_blocking_record_and_dependency():
    ledger = _posted_ledger("TEST")
    db = SessionLocal()
    try:
        db.execute(text("CREATE TABLE IF NOT EXISTS test_sales_cleanup_dependency(id TEXT PRIMARY KEY,sales_ledger_id TEXT)"))
        db.execute(text("DELETE FROM test_sales_cleanup_dependency"))
        db.execute(text("INSERT INTO test_sales_cleanup_dependency(id,sales_ledger_id) VALUES(:id,:ledger_id)"), {"id": uuid4().hex, "ledger_id": ledger["id"]})
        db.commit()
        response = client.post(
            "/api/sales-ledger/admin/cleanup-test-data",
            json={
                "ledger_ids": [ledger["id"]],
                "operator": "super-admin",
                "reason": "dependency test",
                "role": "SUPER_ADMIN",
                "confirmation": "DELETE TEST DATA",
            },
        )
        assert response.status_code == 409, response.text
        detail = response.json()["detail"]
        assert detail["deleted"] == 0
        assert detail["failures"][0]["request_no"] == ledger["request_no"]
        assert "test_sales_cleanup_dependency.sales_ledger_id" in detail["failures"][0]["reason"]
    finally:
        db.execute(text("DROP TABLE IF EXISTS test_sales_cleanup_dependency"))
        db.commit()
        db.close()


def test_bulk_void_preserves_record_and_writes_void_status():
    ledger = _posted_ledger("VOIDTEST")
    response = client.post(
        "/api/sales-ledger/bulk-void",
        json={
            "ledger_ids": [ledger["id"]],
            "operator": "ledger-admin",
            "reason": "business cancellation",
        },
    )
    assert response.status_code == 200, response.text
    record = client.get(f"/api/sales-ledger/{ledger['id']}").json()
    assert record["status"] == "VOID"
    assert record["voided_by"] == "ledger-admin"
    assert record["void_reason"] == "business cancellation"


def test_workbench_exposes_guarded_admin_controls():
    html = client.get("/requests/review-workbench").text
    assert "salesLedgerAdminActions" in html
    assert "/api/sales-ledger/bulk-void" in html
    assert "/api/sales-ledger/admin/cleanup-test-data" in html
    assert "DELETE TEST DATA" in html

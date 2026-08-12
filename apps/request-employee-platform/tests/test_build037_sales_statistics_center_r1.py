import os
import tempfile
from pathlib import Path
from uuid import uuid4


TEST_DB = Path(tempfile.gettempdir()) / f"tlc_sales_statistics_{uuid4().hex}.sqlite3"
os.environ["TLC_DATABASE_URL"] = "sqlite:///" + TEST_DB.as_posix()
os.environ["TLC_DOCUMENT_ROOT"] = str(Path(tempfile.gettempdir()) / "tlc_sales_statistics_documents")

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _approve_sales(request_no: str, request_date: str, customer_id: str, total: str):
    taxable = str(int(total) * 100 // 110)
    tax = str(int(total) - int(taxable))
    payload = {
        "matched": True,
        "request_no": request_no,
        "difference_count": 0,
        "sources": {"excel": request_no + ".xlsx", "pdf": request_no + ".pdf"},
        "request_document": {
            "request_no": request_no,
            "request_date": request_date,
            "customer_id": customer_id,
            "customer_name": customer_id + " Name",
            "currency": "JPY",
            "subtotal": taxable,
            "tax_amount": tax,
            "total_amount": total,
            "taxable_amount_10": taxable,
            "tax_amount_10": tax,
            "tax_inclusive_amount_10": total,
        },
    }
    created = client.post("/api/requests/pending-review", json=payload)
    assert created.status_code == 200, created.text
    record_id = created.json()["record"]["id"]
    approved = client.post(
        f"/api/requests/pending-review/{record_id}/resolve",
        json={"action": "APPROVE", "reviewed_by": "statistics-test", "note": "approved"},
    )
    assert approved.status_code == 200, approved.text
    rows = client.get("/api/sales-ledger", params={"request_no": request_no}).json()
    assert len(rows) == 1
    return rows[0]


def test_sales_statistics_uses_formal_sales_ledger_and_active_default():
    token = uuid4().hex[:8]
    first = _approve_sales(f"REQ-STATS-A-{token}", "2026-07-10", "CUST-STATS-A", "1100")
    _approve_sales(f"REQ-STATS-B-{token}", "2026-08-10", "CUST-STATS-B", "2200")
    voided = client.post(
        "/api/sales-ledger/bulk-void",
        json={"ledger_ids": [first["id"]], "operator": "statistics-test", "reason": "exclude void"},
    )
    assert voided.status_code == 200, voided.text

    active = client.get("/api/sales-ledger/statistics/summary")
    assert active.status_code == 200, active.text
    body = active.json()
    assert body["filters"]["status"] == "ACTIVE"
    assert body["summary"]["count"] == 1
    assert body["summary"]["total_amount"] == "2200"
    assert body["by_month"][0]["business_month"] == "2026-08"

    all_rows = client.get("/api/sales-ledger/statistics/summary", params={"status": ""}).json()
    assert all_rows["summary"]["count"] == 2
    assert all_rows["summary"]["total_amount"] == "3300"


def test_sales_statistics_filters_and_page_contract():
    token = uuid4().hex[:8]
    _approve_sales(f"REQ-STATS-C-{token}", "2026-06-15", "CUST-STATS-C", "3300")
    result = client.get(
        "/api/sales-ledger/statistics/summary",
        params={"date_from": "2026-06-01", "date_to": "2026-06-30", "customer_id": "CUST-STATS-C"},
    )
    assert result.status_code == 200, result.text
    assert result.json()["summary"]["count"] == 1
    html = client.get("/sales").text
    assert "销售统计中心" in html
    assert "/api/sales-ledger/statistics/summary" in html
    assert "formal_sales_request_ledger" in html
    assert "fetch('/api/sales')" not in html

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

ROW = {
    "customer_id": "CSV-T002-002",
    "customer_name": "CSV 東京顧客 Alpha",
    "request_date_cutoff": "2026-07-31",
    "bank_received_date_cutoff": "2026-08-05",
    "request_total_amount": "1234",
    "bank_receipt_amount": "1000",
    "cash_receipt_amount": "234",
    "special_writeoff_amount": "0",
    "manual_adjustment_amount": "0",
    "currency": "JPY",
    "status": "confirmed",
    "confirmed_by": "csv-test",
    "note": "中文 日本語 English",
}


def setup_module():
    response = client.post("/api/customer-reconciliation/cutoffs", json=ROW)
    assert response.status_code in (200, 201)


def test_customer_reconciliation_csv_export_endpoint_uses_export_engine():
    response = client.get(
        "/api/customer-reconciliation/cutoffs/export/csv",
        params={"customer_id": "T002", "lang": "zh"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "customer_reconciliation_cutoffs.csv" in response.headers.get("content-disposition", "")
    text = response.content.decode("utf-8-sig")
    assert "客户ID" in text
    assert "CSV-T002-002" in text
    assert "合计" in text
    assert "Edit" not in text
    assert "Action" not in text

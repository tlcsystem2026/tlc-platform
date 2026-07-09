from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

ROW = {
    "customer_id": "PDF-T004-002",
    "customer_name": "PDF 東京顧客 Alpha",
    "request_date_cutoff": "2026-07-31",
    "bank_received_date_cutoff": "2026-08-05",
    "request_total_amount": "3234",
    "bank_receipt_amount": "3000",
    "cash_receipt_amount": "234",
    "special_writeoff_amount": "0",
    "manual_adjustment_amount": "0",
    "currency": "JPY",
    "status": "confirmed",
    "confirmed_by": "pdf-test",
    "note": "中文 日本語 English",
}


def setup_module():
    response = client.post("/api/customer-reconciliation/cutoffs", json=ROW)
    assert response.status_code in (200, 201)


def bomhex(text: str) -> bytes:
    return ("feff" + text.encode("utf-16-be").hex()).encode("ascii")


def test_customer_reconciliation_pdf_export_endpoint_uses_export_engine():
    response = client.get(
        "/api/customer-reconciliation/cutoffs/export/pdf",
        params={"customer_id": "T004", "lang": "zh"},
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert b"TLC-EXPORT-CHECK" in response.content
    assert bomhex("客户ID") in response.content
    assert bomhex("PDF-T004-002") in response.content
    assert bomhex("合计") in response.content

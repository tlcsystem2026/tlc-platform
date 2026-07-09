from fastapi.testclient import TestClient
from zipfile import ZipFile
from io import BytesIO
from src.main import app

client = TestClient(app)

ROW = {
    "customer_id": "XLS-T003-003",
    "customer_name": "Excel 東京顧客 Alpha",
    "request_date_cutoff": "2026-07-31",
    "bank_received_date_cutoff": "2026-08-05",
    "request_total_amount": "2234",
    "bank_receipt_amount": "2000",
    "cash_receipt_amount": "234",
    "special_writeoff_amount": "0",
    "manual_adjustment_amount": "0",
    "currency": "JPY",
    "status": "confirmed",
    "confirmed_by": "excel-test",
    "note": "中文 日本語 English",
}


def setup_module():
    response = client.post("/api/customer-reconciliation/cutoffs", json=ROW)
    assert response.status_code in (200, 201)


def _xlsx_text(content: bytes) -> str:
    with ZipFile(BytesIO(content)) as zf:
        parts = []
        for name in zf.namelist():
            if name.endswith(".xml"):
                parts.append(zf.read(name).decode("utf-8", errors="ignore"))
        return "\n".join(parts)


def test_customer_reconciliation_excel_export_endpoint_uses_export_engine_without_openpyxl():
    response = client.get(
        "/api/customer-reconciliation/cutoffs/export/excel",
        params={"customer_id": "T003", "lang": "zh"},
    )
    assert response.status_code == 200
    assert response.content[:2] == b"PK"
    disposition = response.headers.get("content-disposition", "")
    assert "customer_reconciliation_cutoffs" in disposition
    assert disposition.endswith('.xlsx"') or ".xlsx" in disposition
    text = _xlsx_text(response.content)
    assert "客户ID" in text
    assert "XLS-T003-003" in text
    assert "合计" in text
    assert "Edit" not in text
    assert "Action" not in text

from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_customer_reconciliation_page_available():
    r = client.get("/api/customer-reconciliation/page")
    assert r.status_code == 200
    assert "客户对账清款基准设置" in r.text
    assert "不是按银行账户设置" in r.text


def test_customer_reconciliation_cutoff_business_flow():
    payload = {
        "customer_id": "CUST-ACCEPT-001",
        "customer_name": "正式测试客户",
        "request_date_cutoff": "2026-07-31",
        "payment_received_date_cutoff": "2026-08-05",
        "confirmed_total_amount": "125000",
        "currency": "JPY",
        "bank_transfer_amount": "100000",
        "cash_collection_amount": "20000",
        "special_writeoff_amount": "5000",
        "manual_adjustment_amount": "0",
        "note": "现金收款与特别核销已经社长确认",
        "confirmed_by": "pytest",
    }
    r = client.post("/api/customer-reconciliation/cutoffs", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["customer_id"] == "CUST-ACCEPT-001"
    assert body["request_date_cutoff"] == "2026-07-31"
    assert body["payment_received_date_cutoff"] == "2026-08-05"
    assert body["next_reconciliation_scope"]["next_request_condition"] == "request_date > 2026-07-31"
    assert body["next_reconciliation_scope"]["next_payment_condition"] == "payment_received_date > 2026-08-05"
    assert "cash_collection" in body["payment_sources"]
    assert "special_writeoff" in body["payment_sources"]

    listed = client.get("/api/customer-reconciliation/cutoffs", params={"customer_id": "CUST-ACCEPT-001"})
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["customer_name"] == "正式测试客户"

    scope = client.get("/api/customer-reconciliation/scope", params={"customer_id": "CUST-ACCEPT-001"})
    assert scope.status_code == 200
    assert scope.json()["excluded_request_rule"] == "exclude requests where request_date <= 2026-07-31"


def test_customer_reconciliation_exports():
    xlsx = client.get("/api/customer-reconciliation/cutoffs/export/excel")
    assert xlsx.status_code == 200
    assert "spreadsheetml.sheet" in xlsx.headers["content-type"]
    with ZipFile(BytesIO(xlsx.content)) as z:
        assert "xl/workbook.xml" in z.namelist()

    pdf = client.get("/api/customer-reconciliation/cutoffs/export/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF-1.4")

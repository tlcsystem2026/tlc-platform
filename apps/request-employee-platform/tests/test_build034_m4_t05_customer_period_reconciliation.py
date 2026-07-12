from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _create_customer(customer_id: str, alias: str):
    response = client.post("/api/tlc-customers", json={
        "customer_id": customer_id,
        "formal_name": f"株式会社{alias}",
        "alias_1": alias,
        "status_code": "ACTIVE",
        "active": True,
    })
    assert response.status_code == 200, response.text


def _create_sales_ledger(customer_id: str, request_no: str, request_date: str, amount: str):
    pending = client.post("/api/requests/pending-review", json={
        "matched": True,
        "request_no": request_no,
        "difference_count": 0,
        "sources": {"excel": request_no + ".xlsx", "pdf": request_no + ".pdf"},
        "request_document": {
            "request_no": request_no,
            "request_date": request_date,
            "customer_id": customer_id,
            "customer_name": "Period Customer",
            "currency": "JPY",
            "subtotal": amount,
            "tax_amount": "0",
            "total_amount": amount,
        },
    })
    assert pending.status_code == 200, pending.text
    record_id = pending.json()["record"]["id"]

    approved = client.post(
        f"/api/requests/pending-review/{record_id}/resolve",
        json={"action": "APPROVE", "reviewed_by": "period-test"},
    )
    assert approved.status_code == 200, approved.text

    posted = client.post(f"/api/sales-ledger/from-pending-review/{record_id}")
    assert posted.status_code == 200, posted.text


def _import_and_match_payment(counterparty: str, tx_id: str, tx_date: str, amount: str):
    csv_body = f"""お客さま口座情報
お客さま口座番号：10190-TEST
取引日,入出金明細ＩＤ,受入金額（円）,払出金額（円）,詳細１,詳細２,現在（貸付）高,
{tx_date.replace("-", "")},{tx_id},{amount},,送金,{counterparty},999999,
""".encode("cp932")

    imported = client.post(
        f"/api/bank-import/csv?source_name={tx_id}.csv",
        content=csv_body,
        headers={"content-type": "text/csv"},
    )
    assert imported.status_code == 200, imported.text

    matched = client.post("/api/customer-bank-matching/run", params={"limit": 1000})
    assert matched.status_code == 200, matched.text


def test_period_reconciliation_uses_exclusive_previous_and_inclusive_current():
    suffix = uuid4().hex[:8]
    customer_id = f"CUST-PERIOD-{suffix}"
    alias = f"PERIOD CUSTOMER {suffix}"
    _create_customer(customer_id, alias)

    # Outside because it equals previous request cutoff.
    _create_sales_ledger(customer_id, f"REQ-OLD-{suffix}", "2026-06-30", "100")
    # Included.
    _create_sales_ledger(customer_id, f"REQ-IN-{suffix}", "2026-07-10", "1000")
    # Included because current cutoff is inclusive.
    _create_sales_ledger(customer_id, f"REQ-END-{suffix}", "2026-07-31", "500")

    # Outside because it equals previous bank cutoff.
    _import_and_match_payment(alias, f"TX-OLD-{suffix}", "2026-06-30", "50")
    # Included.
    _import_and_match_payment(alias, f"TX-IN-{suffix}", "2026-07-15", "900")
    # Included because current cutoff is inclusive.
    _import_and_match_payment(alias, f"TX-END-{suffix}", "2026-07-31", "200")

    response = client.get("/api/customer-payment-reconciliation/summary", params={
        "customer_id": customer_id,
        "previous_request_cutoff": "2026-06-30",
        "current_request_cutoff": "2026-07-31",
        "previous_bank_cutoff": "2026-06-30",
        "current_bank_cutoff": "2026-07-31",
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sales_count"] == 2
    assert body["sales_total"] == "1500"
    assert body["payment_count"] == 2
    assert body["payment_total"] == "1100"
    assert body["period_outstanding"] == "400"
    assert body["status"] == "PARTIAL"


def test_invalid_period_is_rejected():
    response = client.get("/api/customer-payment-reconciliation/summary", params={
        "customer_id": "C001",
        "previous_request_cutoff": "2026-07-31",
        "current_request_cutoff": "2026-07-01",
        "previous_bank_cutoff": "2026-06-30",
        "current_bank_cutoff": "2026-07-31",
    })
    assert response.status_code == 400


def test_reconciliation_page_available():
    response = client.get("/customer-payment-reconciliation")
    assert response.status_code == 200
    assert "客户销售与入金区间核对" in response.text
    assert "/api/customer-payment-reconciliation/summary" in response.text
    assert "/tlc-customer-master" in response.text

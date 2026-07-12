from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _create_sales(customer_id: str, request_no: str, request_date: str, amount: str):
    pending = client.post("/api/requests/pending-review", json={
        "matched": True,
        "request_no": request_no,
        "difference_count": 0,
        "sources": {"excel": request_no + ".xlsx", "pdf": request_no + ".pdf"},
        "request_document": {
            "request_no": request_no,
            "request_date": request_date,
            "customer_id": customer_id,
            "customer_name": "Carry Forward Customer",
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
        json={"action": "APPROVE", "reviewed_by": "carry-forward-test"},
    )
    assert approved.status_code == 200, approved.text

    posted = client.post(f"/api/sales-ledger/from-pending-review/{record_id}")
    assert posted.status_code == 200, posted.text


def test_reconciliation_can_be_saved_and_carried_forward():
    suffix = uuid4().hex[:10]
    customer_id = f"CUST-CARRY-{suffix}"

    _create_sales(customer_id, f"REQ-CARRY-1-{suffix}", "2026-07-10", "1000")

    first = client.post("/api/customer-payment-reconciliation/confirm", json={
        "customer_id": customer_id,
        "previous_request_cutoff": "2026-06-30",
        "current_request_cutoff": "2026-07-31",
        "previous_bank_cutoff": "2026-06-30",
        "current_bank_cutoff": "2026-07-31",
        "opening_outstanding": "200",
        "confirmed_by": "tester",
        "note": "first period",
    })
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "saved"
    assert body["record"]["opening_outstanding"] == "200"
    assert body["record"]["period_sales_total"] == "1000"
    assert body["record"]["period_payment_total"] == "0"
    assert body["record"]["closing_outstanding"] == "1200"
    assert body["record"]["status"] == "UNPAID"

    _create_sales(customer_id, f"REQ-CARRY-2-{suffix}", "2026-08-10", "300")

    second_calc = client.get("/api/customer-payment-reconciliation/calculate", params={
        "customer_id": customer_id,
        "previous_request_cutoff": "2026-07-31",
        "current_request_cutoff": "2026-08-31",
        "previous_bank_cutoff": "2026-07-31",
        "current_bank_cutoff": "2026-08-31",
    })
    assert second_calc.status_code == 200, second_calc.text
    second_body = second_calc.json()
    assert second_body["opening_outstanding"] == "1200"
    assert second_body["sales_total"] == "300"
    assert second_body["closing_outstanding"] == "1500"
    assert second_body["carry_forward_source"]["reconciliation_id"] == body["record"]["id"]


def test_duplicate_period_save_is_idempotent():
    suffix = uuid4().hex[:10]
    customer_id = f"CUST-IDEMP-{suffix}"

    payload = {
        "customer_id": customer_id,
        "previous_request_cutoff": "2026-01-01",
        "current_request_cutoff": "2026-01-31",
        "previous_bank_cutoff": "2026-01-01",
        "current_bank_cutoff": "2026-01-31",
        "opening_outstanding": "0",
        "confirmed_by": "tester",
    }

    first = client.post("/api/customer-payment-reconciliation/confirm", json=payload)
    second = client.post("/api/customer-payment-reconciliation/confirm", json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["status"] == "saved"
    assert second.json()["status"] == "exists"
    assert first.json()["record"]["id"] == second.json()["record"]["id"]


def test_confirmed_by_is_required():
    response = client.post("/api/customer-payment-reconciliation/confirm", json={
        "customer_id": "C001",
        "previous_request_cutoff": "2026-01-01",
        "current_request_cutoff": "2026-01-31",
        "previous_bank_cutoff": "2026-01-01",
        "current_bank_cutoff": "2026-01-31",
    })
    assert response.status_code == 400


def test_confirm_page_available():
    response = client.get("/customer-payment-reconciliation/confirm")
    assert response.status_code == 200
    assert "客户对账确认与结转" in response.text
    assert "/api/customer-payment-reconciliation/confirm" in response.text
    assert "/api/customer-payment-reconciliation/history" in response.text

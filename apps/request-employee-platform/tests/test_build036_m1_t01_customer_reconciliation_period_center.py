
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_calculate_empty_sources_creates_zero_snapshot():
    customer_id = f"C-{uuid4().hex[:10]}"
    response = client.post(
        "/api/tlc-customer-reconciliation-snapshots/calculate",
        json={
            "customer_id": customer_id,
            "customer_name": "Test Customer",
            "previous_request_cutoff": "2026-01-31",
            "current_request_cutoff": "2026-02-28",
            "previous_bank_cutoff": "2026-01-31",
            "current_bank_cutoff": "2026-02-28",
            "created_by": "tester",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["customer_id"] == customer_id
    assert body["sales_total"] == "0"
    assert body["payment_total"] == "0"
    assert body["unpaid_amount"] == "0"


def test_invalid_period_is_rejected():
    response = client.post(
        "/api/tlc-customer-reconciliation-snapshots/calculate",
        json={
            "customer_id": f"C-{uuid4().hex[:10]}",
            "previous_request_cutoff": "2026-02-28",
            "current_request_cutoff": "2026-01-31",
            "previous_bank_cutoff": "2026-01-31",
            "current_bank_cutoff": "2026-02-28",
            "created_by": "tester",
        },
    )
    assert response.status_code == 400
    assert "current cutoff must be after previous cutoff" in response.json()["detail"]


def test_page_available_and_connected():
    response = client.get("/customer-reconciliation-period-center")
    assert response.status_code == 200
    html = response.text
    assert "Customer Reconciliation Period Center" in html
    assert "/api/tlc-customer-reconciliation-snapshots/calculate" in html
    assert 'href="/customer-reconciliation-workbench"' in html
    assert 'href="/business-operations-home"' in html


from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_empty_source_returns_zero_evidence():
    customer_id = f"C-{uuid4().hex[:10]}"
    response = client.get(
        "/api/tlc-sales-ledger-evidence",
        params={
            "customer_id": customer_id,
            "previous_cutoff": "2026-01-31",
            "current_cutoff": "2026-02-28",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["customer_id"] == customer_id
    assert body["record_count"] == 0
    assert body["sales_total"] == "0"
    assert body["records"] == []


def test_invalid_period_is_rejected():
    response = client.get(
        "/api/tlc-sales-ledger-evidence",
        params={
            "customer_id": f"C-{uuid4().hex[:10]}",
            "previous_cutoff": "2026-02-28",
            "current_cutoff": "2026-01-31",
        },
    )
    assert response.status_code == 400
    assert "current cutoff must be after previous cutoff" in response.json()["detail"]


def test_page_available_and_connected():
    response = client.get("/sales-ledger-evidence-center")
    assert response.status_code == 200
    html = response.text
    assert "Sales Ledger Evidence Center" in html
    assert "/api/tlc-sales-ledger-evidence" in html
    assert 'href="/customer-reconciliation-period-center"' in html
    assert 'href="/business-operations-home"' in html

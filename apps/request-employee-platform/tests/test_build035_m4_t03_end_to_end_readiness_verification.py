
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _unique_month():
    value = uuid4().int
    year = 4000 + (value % 5000)
    month = 1 + ((value // 5000) % 12)
    return f"{year:04d}-{month:02d}"


def _batch(month: str):
    response = client.post("/api/tlc-batches", json={
        "business_month": month,
        "title": f"Readiness {uuid4().hex[:8]}",
        "created_by": "tester",
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_month_is_not_ready():
    month = _unique_month()
    response = client.get(
        "/api/tlc-end-to-end-readiness",
        params={"business_month": month},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ready"] is False
    assert body["status"] == "NOT_READY"
    assert body["failed_count"] >= 1
    assert any(
        item["code"] == "BATCH_EXISTS"
        for item in body["failed_checks"]
    )


def test_created_batch_passes_batch_exists_only():
    month = _unique_month()
    _batch(month)

    response = client.get(
        "/api/tlc-end-to-end-readiness",
        params={"business_month": month},
    )
    assert response.status_code == 200
    body = response.json()

    checks = {item["code"]: item for item in body["checks"]}
    assert checks["BUSINESS_MONTH_EXISTS"]["passed"] is True
    assert checks["BATCH_EXISTS"]["passed"] is True
    assert checks["ALL_BATCHES_FINISHED"]["passed"] is False
    assert body["ready"] is False


def test_readiness_page_available_and_connected():
    response = client.get("/end-to-end-readiness")
    assert response.status_code == 200
    html = response.text
    assert "End-to-End Readiness Verification" in html
    assert "/api/tlc-end-to-end-readiness" in html
    assert 'href="/guided-monthly-workflow"' in html
    assert 'href="/business-operations-home"' in html
    assert 'href="/operational-exception-dashboard"' in html
    assert 'href="/monthly-close-center"' in html

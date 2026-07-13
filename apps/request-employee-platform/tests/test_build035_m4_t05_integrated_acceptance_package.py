
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _unique_month():
    value = uuid4().int
    year = 6000 + (value % 3000)
    month = 1 + ((value // 3000) % 12)
    return f"{year:04d}-{month:02d}"


def test_acceptance_returns_all_areas_for_empty_month():
    month = _unique_month()

    response = client.get(
        "/api/tlc-build035-acceptance",
        params={"business_month": month},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["business_month"] == month
    assert body["area_count"] == 12
    assert len(body["areas"]) == 12
    assert any(item["code"] == "BATCH" for item in body["areas"])
    assert any(item["code"] == "RESET_REPLAY" for item in body["areas"])


def test_acceptance_run_is_recorded():
    month = _unique_month()

    run = client.post(
        "/api/tlc-build035-acceptance/runs",
        json={
            "business_month": month,
            "operator": "tester",
        },
    )
    assert run.status_code == 200, run.text
    assert run.json()["run"]["business_month"] == month

    rows = client.get(
        "/api/tlc-build035-acceptance/runs",
        params={"business_month": month},
    )
    assert rows.status_code == 200
    assert len(rows.json()) == 1
    assert rows.json()[0]["operator"] == "tester"


def test_acceptance_page_available_and_connected():
    response = client.get("/build035-acceptance")
    assert response.status_code == 200
    html = response.text
    assert "Build035 Integrated Acceptance" in html
    assert "/api/tlc-build035-acceptance" in html
    assert 'href="/business-operations-home"' in html
    assert 'href="/guided-monthly-workflow"' in html
    assert 'href="/end-to-end-readiness"' in html
    assert 'href="/business-test-replay"' in html

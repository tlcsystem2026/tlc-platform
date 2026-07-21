from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_review_api_accepts_latest_only_parameter():
    response = client.get(
        "/api/tlc-request-reviews",
        params={
            "business_month": "190001",
            "latest_only": "true",
            "review_status": "",
        },
    )
    assert response.status_code == 200
    assert response.json() == []


def test_review_page_defaults_to_latest_batch():
    response = client.get("/request-review-center")
    assert response.status_code == 200
    html = response.text
    assert 'id="latestBatchOnly"' in html
    assert 'type="checkbox" checked' in html
    assert "仅显示最新 Batch" in html
    assert 'latest_only:$(\"latestBatchOnly\").checked' in html
    assert "默认仅显示所选业务年月中最新一次 Batch" in html


def test_service_contains_latest_batch_selection():
    service = (
        Path(__file__).parents[1]
        / "src/services/request_review_service.py"
    ).read_text(encoding="utf-8")
    assert "BUILD037_BATCH_REVIEW_LATEST_R1" in service
    assert "BUILD037_BATCH_REVIEW_TABLE_GUARD_R2" in service
    assert "sqlite_master" in service
    assert "GROUP BY batch_id" in service
    assert "MAX(COALESCE(created_at,'')) DESC" in service
    assert "MAX(rowid) DESC" in service

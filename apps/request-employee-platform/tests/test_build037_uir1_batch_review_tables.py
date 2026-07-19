from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_build037_uir1_review_api_accepts_batch_filter():
    response = client.get(
        "/api/tlc-request-reviews",
        params={
            "batch_id": "__TLC_NON_EXISTENT_BATCH__",
            "review_status": "",
        },
    )
    assert response.status_code == 200
    assert response.json() == []


def test_build037_uir1_unified_page_controls():
    response = client.get("/request-review-center")
    assert response.status_code == 200
    html = response.text
    assert 'id="latestBatchOnly"' in html
    assert "batchRunning" in html
    assert 'btn.disabled=true' in html
    assert 'btn.textContent="执行中..."' in html
    assert 'batch_id:$("latestBatchOnly").checked?activeBatchId:""' in html


def test_build037_uir1_all_static_tables_have_row_selector():
    static_dir = Path(__file__).parents[1] / "src" / "web" / "static"
    table_pages = []
    for page in static_dir.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        if "<table" in text.lower():
            table_pages.append(page.name)
            assert "TLC_TABLE_ROW_SELECTOR_V1" in text, page.name
    assert table_pages

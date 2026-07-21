from pathlib import Path


APP = Path(__file__).parents[1]


def test_backend_forces_latest_batch_for_month():
    service = (
        APP / "src/services/request_review_service.py"
    ).read_text(encoding="utf-8")
    assert "BUILD037_BATCH_REVIEW_FORCE_LATEST_R3" in service
    assert "if business_month and latest_only:" in service
    assert "ORDER BY MAX(rowid) DESC" in service
    assert "batch_id=(" in service


def test_page_defaults_to_latest_and_does_not_send_stale_batch_id():
    html = (
        APP / "src/web/static/request_review_center.html"
    ).read_text(encoding="utf-8")
    assert 'id="latestBatchOnly"' in html
    assert 'type="checkbox" checked' in html
    assert "仅显示最新 Batch" in html
    assert 'batch_id:""' in html
    assert 'latest_only:$("latestBatchOnly").checked' in html
    assert "Batch Review 显示规则：R3（默认最新一次）" in html


def test_route_passes_latest_only_to_service():
    route = (
        APP / "src/api/routes/request_review.py"
    ).read_text(encoding="utf-8")
    assert "latest_only:bool=True" in route.replace(" ", "")
    assert "batch_id,latest_only,review_status" in route.replace(" ", "")

from pathlib import Path


APP = Path(__file__).parents[1]


def test_backend_forces_latest_batch_for_month():
    service = (
        APP / "src/services/request_review_service.py"
    ).read_text(encoding="utf-8")
    assert "BUILD037_BATCH_REVIEW_FORCE_LATEST_R3" in service
    assert "if business_month and latest_only:" in service
    assert "ORDER BY MAX(rowid) DESC" in service


def test_visible_latest_control_is_under_queue_heading():
    html = (
        APP / "src/web/static/request_review_center.html"
    ).read_text(encoding="utf-8")

    heading = html.index("Batch Review Queue 预览")
    toolbar = html.index('id="latestBatchToolbar"')
    checkbox = html.index('id="latestBatchOnly"')

    assert heading < toolbar < checkbox
    assert html.count('id="latestBatchOnly"') == 1
    assert 'type="checkbox" checked' in html
    assert "仅显示最新 Batch" in html
    assert "显示规则：R4" in html
    assert 'batch_id:""' in html
    assert 'latest_only:$("latestBatchOnly").checked' in html


def test_route_passes_latest_only_to_service():
    route = (
        APP / "src/api/routes/request_review.py"
    ).read_text(encoding="utf-8")
    compact = route.replace(" ", "")
    assert "latest_only:bool=True" in compact
    assert "batch_id,latest_only,review_status" in compact

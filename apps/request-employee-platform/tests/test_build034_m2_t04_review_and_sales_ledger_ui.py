from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_request_review_workbench_page_available():
    response = client.get("/requests/review-workbench")

    assert response.status_code == 200
    html = response.text
    assert "销售请求书审核工作台" in html
    assert "/api/requests/pending-review" in html
    assert "/api/requests/pending-review/${id}/resolve" in html
    assert "/api/sales-ledger/from-pending-review/${id}" in html
    assert "/api/sales-ledger?" in html
    assert "MARK_DUPLICATE" in html
    assert "进入正式台账" in html

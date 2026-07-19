from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_review_table_does_not_duplicate_no_and_checkbox_columns():
    response = client.get("/request-review-center")
    assert response.status_code == 200
    html = response.text

    assert '<th class="tlc-row-no">No</th>' in html
    assert '<th class="tlc-row-check"><input type="checkbox" id="selectAllReviews"' in html
    assert '<td class="tlc-row-no">${i+1}</td>' in html
    assert '<td class="tlc-row-check"><input type="checkbox" class="review-select"' in html

    assert '<table><tr><th>No</th><th><input type="checkbox" id="selectAllReviews"' not in html

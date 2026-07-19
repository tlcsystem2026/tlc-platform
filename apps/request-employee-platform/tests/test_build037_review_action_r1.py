from fastapi.testclient import TestClient
from src.main import app
client=TestClient(app)

def test_page_bulk_controls():
    r=client.get("/request-review-center")
    assert r.status_code==200
    h=r.text
    assert 'id="bulkOperator"' in h
    assert "批量核对通过" in h
    assert "selectAllReviews" in h
    assert 'reviewApi+"/batch"' in h

def test_batch_endpoint_requires_ids():
    r=client.put("/api/tlc-request-reviews/batch",json={"review_ids":[],"review_status":"REVIEWED_OK","operator":"TEST","comment":"","forced":False})
    assert r.status_code==400
    assert "review_ids is required" in r.text

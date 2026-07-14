from fastapi.testclient import TestClient
from src.main import app
client = TestClient(app)

def test_page_and_empty_batch(tmp_path, monkeypatch):
    monkeypatch.setenv("TLC_CONFIG_ROOT", str(tmp_path / "config"))
    response = client.put("/api/tlc-system-parameters/request-folders", json={
        "request_root_path": str(tmp_path / "request"),
        "request_incoming_dir": "Incoming",
        "request_processing_dir": "Processing",
        "request_completed_dir": "Completed",
        "request_error_dir": "Error",
        "request_archive_dir": "Archive",
        "request_month_folder_format": "YYYYMM",
    })
    assert response.status_code == 200, response.text
    run = client.post("/api/tlc-request-batch-compare-import/run", json={"business_month": "202601", "operator": "tester"})
    assert run.status_code == 200, run.text
    assert run.json()["review_count"] == 0
    page = client.get("/request-batch-compare-import-center")
    assert page.status_code == 200
    assert "/api/tlc-request-batch-compare-import" in page.text

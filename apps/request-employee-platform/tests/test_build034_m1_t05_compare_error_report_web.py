from pathlib import Path
from fastapi.testclient import TestClient

from src.main import app
from src.services.request_compare_error_report_service import (
    build_error_report_csv,
    build_error_report_html,
    build_error_report_json,
    write_error_report_files,
)

client = TestClient(app)

MISMATCH = {
    "matched": False,
    "request_no": "REQ-T05-001",
    "excel_source": "request.xlsx",
    "pdf_source": "request.pdf",
    "differences": [{
        "field": "total_amount",
        "excel_value": "1100",
        "pdf_value": "1200",
        "severity": "error",
        "message": "total_amount mismatch",
    }],
}
MATCHED = {"matched": True, "request_no": "REQ-T05-002", "differences": []}


def test_error_report_json_csv_and_html():
    json_body = build_error_report_json(MISMATCH)
    csv_body = build_error_report_csv(MISMATCH)
    html_body = build_error_report_html(MISMATCH)
    assert json_body is not None and b"REQ-T05-001" in json_body
    assert csv_body is not None and b"total_amount" in csv_body
    assert "REQ-T05-001" in html_body
    assert "request.xlsx" in html_body
    assert "request.pdf" in html_body


def test_matched_result_does_not_generate_error_files(tmp_path: Path):
    assert build_error_report_json(MATCHED) is None
    assert build_error_report_csv(MATCHED) is None
    assert write_error_report_files(MATCHED, output_dir=tmp_path) == {}


def test_write_error_report_files(tmp_path: Path):
    paths = write_error_report_files(MISMATCH, output_dir=tmp_path)
    assert set(paths) == {"json", "csv", "html"}
    assert all(Path(path).exists() for path in paths.values())


def test_web_error_report_page_and_download_endpoints():
    page = client.post("/api/requests/compare-report/page", json=MISMATCH)
    assert page.status_code == 200
    assert "REQ-T05-001" in page.text
    assert "total_amount" in page.text

    json_response = client.post("/api/requests/compare-report/json", json=MISMATCH)
    assert json_response.status_code == 200
    assert "request_compare_errors.json" in json_response.headers.get("content-disposition", "")

    csv_response = client.post("/api/requests/compare-report/csv", json=MISMATCH)
    assert csv_response.status_code == 200
    assert "request_compare_errors.csv" in csv_response.headers.get("content-disposition", "")

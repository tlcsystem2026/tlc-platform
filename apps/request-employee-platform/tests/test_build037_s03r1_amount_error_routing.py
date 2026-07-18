from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook

from src.main import app
from src.services import request_batch_compare_import_service as service


client = TestClient(app)


PDF_TEXT = """
請 求 書
請求日 2026年1月10日
請求書番号 LY01071
株式会社大通国際 御中
東京恋人株式会社
T9011401020619
ご請求額（①＋②） ¥650,400
税込額① 2,400
税込額② ¥648,000
ご請求額（①＋②） ¥650,400
"""


def _make_excel(path: Path, total: float = 650400.0) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet["G39"] = "ご請求額（①＋②）"
    sheet["I39"] = total
    sheet["G6"] = "東京恋人株式会社"
    sheet["B5"] = "株式会社大通国際"
    workbook.save(path)
    workbook.close()


def test_ly01071_total_uses_invoice_label_not_corporate_number(tmp_path):
    excel = tmp_path / "東京恋人請求書_税込_LY01071_0110_大通_Y0131.xlsx"
    _make_excel(excel)

    data = service._extract_excel(excel)

    assert service._pdf_labeled_total(PDF_TEXT) == "650400"
    assert service._excel_labeled_total(data) == "650400"
    assert service._pdf_labeled_total(PDF_TEXT) != "9011401020619"


def test_exception_pair_moves_to_error_date_batch_folder(tmp_path, monkeypatch):
    config_root = tmp_path / "config"
    request_root = tmp_path / "Request"
    monkeypatch.setenv("TLC_CONFIG_ROOT", str(config_root))

    settings = client.put(
        "/api/tlc-system-parameters/request-folders",
        json={
            "request_root_path": str(request_root),
            "request_incoming_dir": "Incoming",
            "request_processing_dir": "Processing",
            "request_completed_dir": "Completed",
            "request_error_dir": "Error",
            "request_archive_dir": "Archive",
            "request_month_folder_format": "YYYYMM",
        },
    )
    assert settings.status_code == 200, settings.text

    incoming = request_root / "Incoming" / "202601"
    incoming.mkdir(parents=True, exist_ok=True)
    pdf = incoming / "mismatch.pdf"
    excel = incoming / "mismatch.xlsx"
    pdf.write_bytes(b"%PDF-1.4 dummy")
    _make_excel(excel, total=650401.0)

    monkeypatch.setattr(service, "_extract_pdf", lambda _: PDF_TEXT)

    response = client.post(
        "/api/tlc-request-batch-compare-import/run",
        json={"business_month": "202601", "operator": "regression"},
    )
    assert response.status_code == 200, response.text
    batch = response.json()
    assert batch["exception_count"] == 1
    assert batch["status"] == "COMPLETED_WITH_ERRORS"

    completed_files = list((request_root / "Completed" / "202601").rglob("*.*"))
    error_files = list((request_root / "Error" / "202601").rglob("*.*"))

    assert not any(path.name in {"mismatch.pdf", "mismatch.xlsx"} for path in completed_files)
    assert any(path.name == "mismatch.pdf" for path in error_files)
    assert any(path.name == "mismatch.xlsx" for path in error_files)
    assert any(path.name.startswith("request_exceptions_202601_") for path in error_files)

    relative_parts = next(path for path in error_files if path.name == "mismatch.pdf").relative_to(
        request_root / "Error" / "202601"
    ).parts
    assert len(relative_parts) >= 3
    assert len(relative_parts[0]) == 8

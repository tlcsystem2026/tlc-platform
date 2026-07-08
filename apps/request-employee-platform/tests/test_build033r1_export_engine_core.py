
from fastapi.responses import Response

from src.services.export_engine import (
    ExportColumn,
    FontManager,
    build_export_model,
    export_csv_model,
    export_pdf_model,
    selfcheck_export_response,
)


def _model():
    return build_export_model(
        title="客户对账清款 Export Engine",
        language="zh",
        filename="build033r1_export_engine",
        columns=[
            ExportColumn("customer_id", "客户ID"),
            ExportColumn("customer_name", "客户名称"),
            ExportColumn("amount", "金额", numeric=True),
        ],
        rows=[
            {"customer_id": "C-001", "customer_name": "東京顧客 Alpha", "amount": "100"},
            {"customer_id": "C-002", "customer_name": "中文客户 Beta", "amount": "200"},
        ],
    )


def test_export_model_visible_rows_and_total():
    model = _model()
    rows = model.export_rows()
    assert rows[0]["客户ID"] == "C-001"
    assert rows[1]["客户名称"] == "中文客户 Beta"
    assert rows[-1]["客户ID"] == "合计"
    assert rows[-1]["金额"] == "300"


def test_font_manager_mixed_language_policy():
    assert FontManager.font_for("ABC", "en") == "Helvetica"
    assert FontManager.font_for("中文客户", "en") == "STSong-Light"
    assert FontManager.font_for("東京かな", "en") == "HeiseiKakuGo-W5"


def test_csv_engine_contains_header_rows_and_total():
    response = export_csv_model(_model())
    assert isinstance(response, Response)
    body = response.body.decode("utf-8-sig")
    assert "客户ID" in body
    assert "C-001" in body
    assert "合计" in body


def test_pdf_engine_reportlab_markers_and_selfcheck():
    response = export_pdf_model(_model())
    assert response.body.startswith(b"%PDF")
    assert b"ReportLab" in response.body
    selfcheck_export_response(response.body, ["客户对账清款 Export Engine", "客户ID", "C-001"])

from src.services.customer_reconciliation_export_adapter import (
    build_customer_reconciliation_export_model,
    customer_reconciliation_columns,
    normalize_customer_reconciliation_row,
)
from src.services.export_engine import export_csv_model, selfcheck_export_content


def _rows():
    return [
        {
            "customer_id": "C-R2A-001",
            "customer_name": "東京顧客 Alpha",
            "request_date_cutoff": "2026-07-31",
            "bank_received_date_cutoff": "2026-08-05",
            "request_total_amount": "1000",
            "bank_receipt_amount": "800",
            "cash_receipt_amount": "200",
            "special_writeoff_amount": "0",
            "manual_adjustment_amount": "0",
            "currency": "JPY",
            "status": "confirmed",
            "confirmed_by": "tester",
            "note": "中文 日本語 English",
            "edit": "must not export",
        }
    ]


def test_customer_reconciliation_columns_multilang():
    assert customer_reconciliation_columns("zh")[0].label == "客户ID"
    assert customer_reconciliation_columns("ja")[0].label == "顧客ID"
    assert customer_reconciliation_columns("en")[0].label == "Customer ID"


def test_customer_reconciliation_export_model_excludes_action_and_totals():
    model = build_customer_reconciliation_export_model(_rows(), language="en")
    rows = model.export_rows()

    assert model.title == "Customer Reconciliation Cutoff"
    assert "Edit" not in model.headers()
    assert "Action" not in model.headers()
    assert rows[0]["Customer ID"] == "C-R2A-001"
    assert rows[-1]["Customer ID"] == "Total"
    assert rows[-1]["Request Total"] == "1000"


def test_normalize_customer_reconciliation_row_removes_ui_fields():
    row = normalize_customer_reconciliation_row(_rows()[0])
    assert "edit" not in row
    assert row["customer_id"] == "C-R2A-001"


def test_customer_reconciliation_export_model_csv_bridge():
    model = build_customer_reconciliation_export_model(_rows(), language="zh")
    response = export_csv_model(model)
    text = response.body.decode("utf-8-sig")
    assert "客户ID" in text
    assert "C-R2A-001" in text
    assert "合计" in text


def test_customer_reconciliation_export_model_pdf_selfcheck():
    model = build_customer_reconciliation_export_model(_rows(), language="zh")
    markers = "\n".join([model.title, model.headers()[0], model.total_label(), model.rows[0]["customer_id"]])
    content = b"".join(("feff" + token.encode("utf-16-be").hex()).encode("ascii") for token in markers.split("\n"))
    selfcheck_export_content(content, [model.title, model.headers()[0], model.total_label(), "C-R2A-001"])

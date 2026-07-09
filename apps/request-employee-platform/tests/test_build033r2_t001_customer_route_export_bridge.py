from src.services.customer_reconciliation_route_export_bridge import (
    build_customer_reconciliation_route_export_model,
    export_customer_reconciliation_csv,
)


def _rows():
    return [
        {
            "customer_id": "C-T001-002",
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
            "edit": "do not export",
            "action": "do not export",
        }
    ]


def test_route_bridge_builds_export_model_without_ui_fields():
    model = build_customer_reconciliation_route_export_model(_rows(), language="en")
    rows = model.export_rows()
    assert model.title == "Customer Reconciliation Cutoff"
    assert "Edit" not in model.headers()
    assert "Action" not in model.headers()
    assert rows[0]["Customer ID"] == "C-T001-002"
    assert rows[-1]["Customer ID"] == "Total"
    assert rows[-1]["Request Total"] == "1000"


def test_route_bridge_csv_uses_export_engine():
    response = export_customer_reconciliation_csv(_rows(), language="zh")
    text = response.body.decode("utf-8-sig")
    assert "客户ID" in text
    assert "C-T001-002" in text
    assert "合计" in text

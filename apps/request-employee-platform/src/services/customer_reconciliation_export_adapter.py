from __future__ import annotations

from typing import Any

from src.services.export_engine import ExportColumn, ExportModel, build_export_model


LABELS = {
    "zh": {
        "title": "客户对账清款基准设置",
        "customer_id": "客户ID",
        "customer_name": "客户名称",
        "request_date_cutoff": "请求日截止",
        "bank_received_date_cutoff": "银行到账日截止",
        "request_total_amount": "请求合计",
        "bank_receipt_amount": "银行入金",
        "cash_receipt_amount": "现金收款",
        "special_writeoff_amount": "特别核销",
        "manual_adjustment_amount": "人工调整",
        "currency": "币种",
        "status": "状态",
        "confirmed_by": "确认人",
        "note": "备注",
    },
    "ja": {
        "title": "顧客消込基準設定",
        "customer_id": "顧客ID",
        "customer_name": "顧客名",
        "request_date_cutoff": "請求日締切",
        "bank_received_date_cutoff": "銀行入金日締切",
        "request_total_amount": "請求合計",
        "bank_receipt_amount": "銀行入金",
        "cash_receipt_amount": "現金回収",
        "special_writeoff_amount": "特別消込",
        "manual_adjustment_amount": "手動調整",
        "currency": "通貨",
        "status": "状態",
        "confirmed_by": "確認者",
        "note": "備考",
    },
    "en": {
        "title": "Customer Reconciliation Cutoff",
        "customer_id": "Customer ID",
        "customer_name": "Customer Name",
        "request_date_cutoff": "Request Date Cutoff",
        "bank_received_date_cutoff": "Bank Received Cutoff",
        "request_total_amount": "Request Total",
        "bank_receipt_amount": "Bank Receipt",
        "cash_receipt_amount": "Cash Receipt",
        "special_writeoff_amount": "Write-off",
        "manual_adjustment_amount": "Manual Adjustment",
        "currency": "Currency",
        "status": "Status",
        "confirmed_by": "Confirmed By",
        "note": "Note",
    },
}

NUMERIC_KEYS = {
    "request_total_amount",
    "bank_receipt_amount",
    "cash_receipt_amount",
    "special_writeoff_amount",
    "manual_adjustment_amount",
}

COLUMN_KEYS = [
    "customer_id",
    "customer_name",
    "request_date_cutoff",
    "bank_received_date_cutoff",
    "request_total_amount",
    "bank_receipt_amount",
    "cash_receipt_amount",
    "special_writeoff_amount",
    "manual_adjustment_amount",
    "currency",
    "status",
    "confirmed_by",
    "note",
]


def customer_reconciliation_columns(language: str = "zh") -> list[ExportColumn]:
    labels = LABELS.get(language, LABELS["zh"])
    return [
        ExportColumn(
            key=key,
            label=labels[key],
            width=22 if key in {"customer_name", "note"} else 16,
            numeric=key in NUMERIC_KEYS,
        )
        for key in COLUMN_KEYS
    ]


def normalize_customer_reconciliation_row(row: dict[str, Any]) -> dict[str, Any]:
    """Keep only fields used by the export model and remove UI-only fields."""
    return {key: row.get(key, "") for key in COLUMN_KEYS}


def build_customer_reconciliation_export_model(
    rows: list[dict[str, Any]],
    *,
    language: str = "zh",
    filename: str = "customer_reconciliation_cutoffs",
    include_total: bool = True,
) -> ExportModel:
    labels = LABELS.get(language, LABELS["zh"])
    normalized_rows = [normalize_customer_reconciliation_row(row) for row in rows]
    return build_export_model(
        title=labels["title"],
        columns=customer_reconciliation_columns(language),
        rows=normalized_rows,
        language=language,
        filename=filename,
        include_total=include_total,
    )

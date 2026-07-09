from __future__ import annotations

from typing import Any
from fastapi.responses import Response

from src.services.customer_reconciliation_export_adapter import (
    build_customer_reconciliation_export_model,
    normalize_customer_reconciliation_row,
)
from src.services.export_engine import ExportModel, export_csv_model, export_excel_model, export_pdf_model


def build_customer_reconciliation_route_export_model(
    rows: list[dict[str, Any]],
    *,
    language: str = "zh",
    filename: str = "customer_reconciliation_cutoffs",
) -> ExportModel:
    normalized = [normalize_customer_reconciliation_row(row) for row in rows]
    return build_customer_reconciliation_export_model(
        normalized,
        language=language,
        filename=filename,
        include_total=True,
    )


def export_customer_reconciliation_excel(
    rows: list[dict[str, Any]],
    *,
    language: str = "zh",
    filename: str = "customer_reconciliation_cutoffs",
) -> Response:
    model = build_customer_reconciliation_route_export_model(rows, language=language, filename=filename)
    return export_excel_model(model)


def export_customer_reconciliation_pdf(
    rows: list[dict[str, Any]],
    *,
    language: str = "zh",
    filename: str = "customer_reconciliation_cutoffs",
) -> Response:
    model = build_customer_reconciliation_route_export_model(rows, language=language, filename=filename)
    return export_pdf_model(model)


def export_customer_reconciliation_csv(
    rows: list[dict[str, Any]],
    *,
    language: str = "zh",
    filename: str = "customer_reconciliation_cutoffs",
) -> Response:
    model = build_customer_reconciliation_route_export_model(rows, language=language, filename=filename)
    return export_csv_model(model)

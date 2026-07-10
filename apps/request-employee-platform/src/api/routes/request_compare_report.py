from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, Response

from src.services.request_compare_error_report_service import (
    build_error_report_csv,
    build_error_report_html,
    build_error_report_json,
)

router = APIRouter(prefix="/api/requests/compare-report", tags=["request-compare-report"])


@router.post("/json")
def compare_report_json(payload: dict):
    body = build_error_report_json(payload)
    if body is None:
        return JSONResponse({"matched": True, "difference_count": 0})
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="request_compare_errors.json"'},
    )


@router.post("/csv")
def compare_report_csv(payload: dict):
    body = build_error_report_csv(payload)
    if body is None:
        return JSONResponse({"matched": True, "difference_count": 0})
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="request_compare_errors.csv"'},
    )


@router.post("/page", response_class=HTMLResponse)
def compare_report_page(payload: dict):
    return HTMLResponse(build_error_report_html(payload))

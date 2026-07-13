
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_build035_acceptance_service import (
    integrated_acceptance,
    list_acceptance_runs,
    record_acceptance_run,
)


router = APIRouter(tags=["tlc-build035-acceptance"])


@router.get("/api/tlc-build035-acceptance")
def acceptance(
    business_month: str = "",
    db: Session = Depends(get_db),
):
    return integrated_acceptance(
        db,
        business_month=business_month,
    )


@router.post("/api/tlc-build035-acceptance/runs")
def execute_run(
    payload: dict,
    db: Session = Depends(get_db),
):
    try:
        return record_acceptance_run(
            db,
            business_month=payload.get("business_month", ""),
            operator=payload.get("operator", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/tlc-build035-acceptance/runs")
def runs(
    business_month: str = "",
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return list_acceptance_runs(
        db,
        business_month=business_month,
        limit=limit,
    )


@router.get("/build035-acceptance", response_class=HTMLResponse)
def page():
    page_path = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "build035_acceptance.html"
    )
    return HTMLResponse(page_path.read_text(encoding="utf-8"))


from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_monthly_close_control_service import (
    monthly_close_overview,
)


router = APIRouter(tags=["tlc-monthly-close-control"])


@router.get("/api/tlc-monthly-close/{business_month}")
def overview(
    business_month: str,
    db: Session = Depends(get_db),
):
    try:
        return monthly_close_overview(db, business_month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/monthly-close-center", response_class=HTMLResponse)
def monthly_close_page():
    page = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "monthly_close_center.html"
    )
    return HTMLResponse(page.read_text(encoding="utf-8"))

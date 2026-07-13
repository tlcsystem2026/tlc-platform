
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_operational_exception_dashboard_service import (
    operational_exception_dashboard,
)


router = APIRouter(tags=["tlc-operational-exception-dashboard"])


@router.get("/api/tlc-operational-exceptions")
def exceptions(
    business_month: str = "",
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    return operational_exception_dashboard(
        db,
        business_month=business_month,
        limit=limit,
    )


@router.get("/operational-exception-dashboard", response_class=HTMLResponse)
def page():
    page_path = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "operational_exception_dashboard.html"
    )
    return HTMLResponse(page_path.read_text(encoding="utf-8"))


from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_end_to_end_readiness_service import (
    end_to_end_readiness,
)


router = APIRouter(tags=["tlc-end-to-end-readiness"])


@router.get("/api/tlc-end-to-end-readiness")
def readiness(
    business_month: str = "",
    db: Session = Depends(get_db),
):
    return end_to_end_readiness(
        db,
        business_month=business_month,
    )


@router.get("/end-to-end-readiness", response_class=HTMLResponse)
def page():
    page_path = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "end_to_end_readiness.html"
    )
    return HTMLResponse(page_path.read_text(encoding="utf-8"))

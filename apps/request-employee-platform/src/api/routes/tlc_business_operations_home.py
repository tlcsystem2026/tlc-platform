
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_business_operations_home_service import (
    business_operations_home,
)


router = APIRouter(tags=["tlc-business-operations-home"])


@router.get("/api/tlc-business-operations-home")
def overview(
    business_month: str = "",
    db: Session = Depends(get_db),
):
    return business_operations_home(
        db,
        business_month=business_month,
    )


@router.get("/business-operations-home", response_class=HTMLResponse)
def page():
    page_path = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "business_operations_home.html"
    )
    return HTMLResponse(page_path.read_text(encoding="utf-8"))

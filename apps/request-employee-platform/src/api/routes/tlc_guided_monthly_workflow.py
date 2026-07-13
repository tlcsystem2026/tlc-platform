
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_guided_monthly_workflow_service import (
    guided_monthly_workflow,
)


router = APIRouter(tags=["tlc-guided-monthly-workflow"])


@router.get("/api/tlc-guided-monthly-workflow")
def workflow(
    business_month: str = "",
    db: Session = Depends(get_db),
):
    return guided_monthly_workflow(
        db,
        business_month=business_month,
    )


@router.get("/guided-monthly-workflow", response_class=HTMLResponse)
def page():
    page_path = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "guided_monthly_workflow.html"
    )
    return HTMLResponse(page_path.read_text(encoding="utf-8"))

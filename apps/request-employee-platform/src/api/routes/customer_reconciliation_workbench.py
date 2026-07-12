from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["customer-reconciliation-workbench"])


@router.get("/customer-reconciliation-workbench", response_class=HTMLResponse)
def customer_reconciliation_workbench():
    page = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "customer_reconciliation_workbench.html"
    )
    return HTMLResponse(page.read_text(encoding="utf-8"))

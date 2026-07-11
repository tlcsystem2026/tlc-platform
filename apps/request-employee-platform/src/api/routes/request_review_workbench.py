from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["request-review-workbench"])


@router.get("/requests/review-workbench", response_class=HTMLResponse)
def request_review_workbench():
    page = Path(__file__).parents[2] / "web" / "static" / "request_review_workbench.html"
    return HTMLResponse(page.read_text(encoding="utf-8"))

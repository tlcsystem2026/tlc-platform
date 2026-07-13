
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_business_test_replay_service import (
    create_replay_scenario,
    list_runs,
    reset_business_month,
)


router = APIRouter(tags=["tlc-business-test-replay"])


@router.post("/api/tlc-business-test/reset")
def reset(payload: dict, db: Session = Depends(get_db)):
    try:
        return reset_business_month(
            db,
            business_month=payload.get("business_month", ""),
            operator=payload.get("operator", ""),
            confirmation=payload.get("confirmation", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/tlc-business-test/replay")
def replay(payload: dict, db: Session = Depends(get_db)):
    try:
        return create_replay_scenario(
            db,
            business_month=payload.get("business_month", ""),
            operator=payload.get("operator", ""),
            scenario_name=payload.get("scenario_name", "STANDARD"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/tlc-business-test/runs")
def runs(
    business_month: str = "",
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return list_runs(
        db,
        business_month=business_month,
        limit=limit,
    )


@router.get("/business-test-replay", response_class=HTMLResponse)
def page():
    page_path = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "business_test_replay.html"
    )
    return HTMLResponse(page_path.read_text(encoding="utf-8"))

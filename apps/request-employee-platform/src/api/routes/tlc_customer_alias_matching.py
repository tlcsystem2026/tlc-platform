
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_customer_alias_matching_service import (
    list_match_results,
    match_customer_name,
    override_match_result,
)


router = APIRouter(
    prefix="/api/tlc-customer-alias-matching",
    tags=["tlc-customer-alias-matching"],
)


@router.post("/match")
def match(payload: dict, db: Session = Depends(get_db)):
    try:
        return match_customer_name(
            db,
            raw_name=payload.get("raw_name", ""),
            operator=payload.get("operator", ""),
            save_result=payload.get("save_result", True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{result_id}/override")
def override(
    result_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    try:
        return override_match_result(
            db,
            result_id=result_id,
            customer_id=payload.get("customer_id", ""),
            operator=payload.get("operator", ""),
            note=payload.get("note", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_results(
    status: str = "",
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        return list_match_results(
            db,
            status=status,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


page_router = APIRouter(tags=["tlc-customer-alias-matching-center"])


@page_router.get(
    "/customer-alias-matching-center",
    response_class=HTMLResponse,
)
def page():
    page_path = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "customer_alias_matching_center.html"
    )
    return HTMLResponse(page_path.read_text(encoding="utf-8"))

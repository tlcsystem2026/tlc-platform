
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_customer_auto_matching_service import (
    generate_auto_matches,
    list_auto_match_audit,
    list_auto_matches,
    update_match_status,
)


router = APIRouter(
    prefix="/api/tlc-customer-auto-matching",
    tags=["tlc-customer-auto-matching"],
)


@router.post("/generate")
def generate(payload: dict, db: Session = Depends(get_db)):
    try:
        return generate_auto_matches(
            db,
            reconciliation_id=payload.get("reconciliation_id", ""),
            operator=payload.get("operator", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{auto_match_id}/status")
def update_status(
    auto_match_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    try:
        return update_match_status(
            db,
            auto_match_id=auto_match_id,
            status=payload.get("status", ""),
            operator=payload.get("operator", ""),
            note=payload.get("note", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_items(
    reconciliation_id: str = "",
    status: str = "",
    limit: int = Query(default=1000, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    try:
        return list_auto_matches(
            db,
            reconciliation_id=reconciliation_id,
            status=status,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{auto_match_id}/audit")
def audit(
    auto_match_id: str,
    limit: int = Query(default=1000, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    return list_auto_match_audit(
        db,
        auto_match_id=auto_match_id,
        limit=limit,
    )


page_router = APIRouter(tags=["tlc-customer-auto-matching-center"])


@page_router.get(
    "/customer-auto-matching-center",
    response_class=HTMLResponse,
)
def page():
    page_path = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "customer_auto_matching_center.html"
    )
    return HTMLResponse(page_path.read_text(encoding="utf-8"))

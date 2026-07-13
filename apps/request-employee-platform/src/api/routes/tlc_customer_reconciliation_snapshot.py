
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_customer_reconciliation_snapshot_service import (
    calculate_snapshot,
    get_snapshot,
    list_snapshots,
)


router = APIRouter(
    prefix="/api/tlc-customer-reconciliation-snapshots",
    tags=["tlc-customer-reconciliation-snapshot"],
)


@router.post("/calculate")
def calculate(payload: dict, db: Session = Depends(get_db)):
    try:
        return calculate_snapshot(
            db,
            customer_id=payload.get("customer_id", ""),
            customer_name=payload.get("customer_name", ""),
            previous_request_cutoff=payload.get(
                "previous_request_cutoff", ""
            ),
            current_request_cutoff=payload.get(
                "current_request_cutoff", ""
            ),
            previous_bank_cutoff=payload.get(
                "previous_bank_cutoff", ""
            ),
            current_bank_cutoff=payload.get(
                "current_bank_cutoff", ""
            ),
            created_by=payload.get("created_by", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_items(
    customer_id: str = "",
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return list_snapshots(
        db,
        customer_id=customer_id,
        limit=limit,
    )


@router.get("/{snapshot_id}")
def detail(
    snapshot_id: str,
    db: Session = Depends(get_db),
):
    try:
        return get_snapshot(db, snapshot_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


page_router = APIRouter(tags=["tlc-customer-reconciliation-period-center"])


@page_router.get(
    "/customer-reconciliation-period-center",
    response_class=HTMLResponse,
)
def page():
    page_path = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "customer_reconciliation_period_center.html"
    )
    return HTMLResponse(page_path.read_text(encoding="utf-8"))

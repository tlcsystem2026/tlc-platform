from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.customer_reconciliation_history_service import (
    calculate_reconciliation_with_carry_forward,
    get_latest_reconciliation,
    list_reconciliations,
    save_reconciliation,
)


router = APIRouter(tags=["customer-reconciliation-history"])


@router.get("/api/customer-payment-reconciliation/calculate")
def calculate(
    customer_id: str,
    previous_request_cutoff: str,
    current_request_cutoff: str,
    previous_bank_cutoff: str,
    current_bank_cutoff: str,
    opening_outstanding: str = "",
    db: Session = Depends(get_db),
):
    try:
        return calculate_reconciliation_with_carry_forward(
            db,
            customer_id=customer_id,
            previous_request_cutoff=previous_request_cutoff,
            current_request_cutoff=current_request_cutoff,
            previous_bank_cutoff=previous_bank_cutoff,
            current_bank_cutoff=current_bank_cutoff,
            opening_outstanding=opening_outstanding,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/customer-payment-reconciliation/confirm")
def confirm(payload: dict, db: Session = Depends(get_db)):
    try:
        return save_reconciliation(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/customer-payment-reconciliation/history")
def history(
    customer_id: str = "",
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return list_reconciliations(
        db,
        customer_id=customer_id,
        limit=limit,
    )


@router.get("/api/customer-payment-reconciliation/latest")
def latest(
    customer_id: str,
    db: Session = Depends(get_db),
):
    return get_latest_reconciliation(db, customer_id) or {}


@router.get("/customer-payment-reconciliation/confirm", response_class=HTMLResponse)
def confirm_page():
    html = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "customer_reconciliation_confirm.html"
    )
    return HTMLResponse(html.read_text(encoding="utf-8"))

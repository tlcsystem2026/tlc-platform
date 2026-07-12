from pathlib import Path
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.customer_period_reconciliation_service import (
    customer_period_reconciliation,
)


router = APIRouter(tags=["customer-period-reconciliation"])


@router.get("/api/customer-payment-reconciliation/summary")
def summary(
    customer_id: str,
    previous_request_cutoff: str,
    current_request_cutoff: str,
    previous_bank_cutoff: str,
    current_bank_cutoff: str,
    db: Session = Depends(get_db),
):
    try:
        return customer_period_reconciliation(
            db,
            customer_id=customer_id,
            previous_request_cutoff=previous_request_cutoff,
            current_request_cutoff=current_request_cutoff,
            previous_bank_cutoff=previous_bank_cutoff,
            current_bank_cutoff=current_bank_cutoff,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/customer-payment-reconciliation", response_class=HTMLResponse)
def page():
    html = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "customer_payment_reconciliation.html"
    )
    return HTMLResponse(html.read_text(encoding="utf-8"))

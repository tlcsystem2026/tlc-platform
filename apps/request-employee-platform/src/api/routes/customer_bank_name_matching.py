from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.customer_bank_name_matching_service import (
    match_customer_by_bank_counterparty,
    match_unassigned_bank_transactions,
)


router = APIRouter(prefix="/api/customer-bank-matching", tags=["customer-bank-matching"])


@router.get("/preview")
def preview(
    counterparty: str,
    db: Session = Depends(get_db),
):
    return match_customer_by_bank_counterparty(db, counterparty).as_dict()


@router.post("/run")
def run_matching(
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return match_unassigned_bank_transactions(db, limit=limit)

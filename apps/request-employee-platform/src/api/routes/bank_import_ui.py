from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.bank_transaction_query_service import (
    list_bank_transactions,
    summarize_bank_transactions,
)

router = APIRouter(tags=["bank-import-ui"])


@router.get("/api/bank-import/transactions")
def transactions(
    bank_code: str = "",
    account_number: str = "",
    direction: str = "",
    transaction_date_from: str = "",
    transaction_date_to: str = "",
    counterparty: str = "",
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return list_bank_transactions(
        db,
        bank_code=bank_code,
        account_number=account_number,
        direction=direction,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
        counterparty=counterparty,
        limit=limit,
    )


@router.get("/api/bank-import/summary")
def summary(
    bank_code: str = "",
    transaction_date_from: str = "",
    transaction_date_to: str = "",
    db: Session = Depends(get_db),
):
    return summarize_bank_transactions(
        db,
        bank_code=bank_code,
        transaction_date_from=transaction_date_from,
        transaction_date_to=transaction_date_to,
    )


@router.get("/bank-import", response_class=HTMLResponse)
def bank_import_page():
    page = Path(__file__).parents[2] / "web" / "static" / "bank_import.html"
    return HTMLResponse(page.read_text(encoding="utf-8"))

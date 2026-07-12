from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_batch_sales_ledger_service import (
    create_ledger_link,
    ledger_summary,
    list_ledger_links,
)

router = APIRouter(prefix="/api/tlc-batches", tags=["tlc-batch-sales-ledger-center"])


@router.post("/{batch_id}/sales-ledger/links")
def create(batch_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return create_ledger_link(
            db,
            batch_id=batch_id,
            review_link_id=payload.get("review_link_id", ""),
            sales_ledger_id=payload.get("sales_ledger_id", ""),
            posted_by=payload.get("posted_by", ""),
            note=payload.get("note", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{batch_id}/sales-ledger/links")
def links(batch_id: str, db: Session = Depends(get_db)):
    try:
        return list_ledger_links(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{batch_id}/sales-ledger/summary")
def summary(batch_id: str, db: Session = Depends(get_db)):
    try:
        return ledger_summary(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

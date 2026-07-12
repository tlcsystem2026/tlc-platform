from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_customer_master_service import (
    get_customer,
    list_customers,
    save_customer,
)


router = APIRouter(tags=["tlc-customer-master"])


@router.get("/api/tlc-customers")
def list_records(
    query: str = "",
    status_code: str = "",
    include_inactive: bool = True,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return list_customers(
        db,
        query=query,
        status_code=status_code,
        include_inactive=include_inactive,
        limit=limit,
    )


@router.get("/api/tlc-customers/{record_id}")
def get_record(record_id: str, db: Session = Depends(get_db)):
    record = get_customer(db, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return record


@router.post("/api/tlc-customers")
def save_record(payload: dict, db: Session = Depends(get_db)):
    try:
        return save_customer(db, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tlc-customer-master", response_class=HTMLResponse)
def page():
    html = Path(__file__).parents[2] / "web" / "static" / "tlc_customer_master.html"
    return HTMLResponse(html.read_text(encoding="utf-8"))

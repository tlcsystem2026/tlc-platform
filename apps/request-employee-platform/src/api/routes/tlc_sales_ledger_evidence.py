
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_sales_ledger_evidence_service import (
    compare_snapshot_sales,
    list_sales_evidence,
)


router = APIRouter(
    prefix="/api/tlc-sales-ledger-evidence",
    tags=["tlc-sales-ledger-evidence"],
)


@router.get("")
def evidence(
    customer_id: str = "",
    customer_name: str = "",
    previous_cutoff: str = "",
    current_cutoff: str = "",
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    try:
        return list_sales_evidence(
            db,
            customer_id=customer_id,
            customer_name=customer_name,
            previous_cutoff=previous_cutoff,
            current_cutoff=current_cutoff,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/snapshot/{snapshot_id}")
def snapshot_evidence(
    snapshot_id: str,
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    try:
        return compare_snapshot_sales(
            db,
            snapshot_id=snapshot_id,
            limit=limit,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


page_router = APIRouter(tags=["tlc-sales-ledger-evidence-center"])


@page_router.get(
    "/sales-ledger-evidence-center",
    response_class=HTMLResponse,
)
def page():
    page_path = (
        Path(__file__).parents[2]
        / "web"
        / "static"
        / "sales_ledger_evidence_center.html"
    )
    return HTMLResponse(page_path.read_text(encoding="utf-8"))

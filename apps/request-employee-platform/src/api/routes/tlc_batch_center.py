from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_batch_service import (
    ALLOWED_STATUSES,
    create_batch,
    get_batch,
    list_batches,
    list_timeline,
    transition_batch,
    update_batch,
)


router = APIRouter(tags=["tlc-batch-center"])


@router.get("/api/tlc-batches/statuses")
def statuses():
    return sorted(ALLOWED_STATUSES)


@router.get("/api/tlc-batches")
def batches(
    business_month: str = "",
    status: str = "",
    query: str = "",
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        return list_batches(
            db,
            business_month=business_month,
            status=status,
            query=query,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/tlc-batches")
def create(payload: dict, db: Session = Depends(get_db)):
    try:
        return create_batch(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/tlc-batches/{batch_id}")
def detail(batch_id: str, db: Session = Depends(get_db)):
    record = get_batch(db, batch_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return record


@router.put("/api/tlc-batches/{batch_id}")
def update(batch_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return update_batch(db, batch_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/tlc-batches/{batch_id}/transition")
def transition(batch_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return transition_batch(
            db,
            batch_id,
            new_status=payload.get("new_status", ""),
            operator=payload.get("operator", ""),
            message=payload.get("message", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/tlc-batches/{batch_id}/timeline")
def timeline(batch_id: str, db: Session = Depends(get_db)):
    try:
        return list_timeline(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/batch-center", response_class=HTMLResponse)
def batch_center_page():
    page = Path(__file__).parents[2] / "web" / "static" / "batch_center.html"
    return HTMLResponse(page.read_text(encoding="utf-8"))

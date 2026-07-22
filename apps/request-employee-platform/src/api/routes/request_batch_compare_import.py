from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.request_batch_compare_import_service import bulk_delete_review_queue, latest_batch, list_review_queue, run_request_batch

router = APIRouter(prefix="/api/tlc-request-batch-compare-import", tags=["tlc-request-batch-compare-import"])

@router.post("/run")
def run(payload: dict, db: Session = Depends(get_db)):
    try:
        return run_request_batch(db, business_month=payload.get("business_month", ""), operator=payload.get("operator", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/latest")
def latest(business_month: str = "", db: Session = Depends(get_db)):
    try:
        return latest_batch(db, business_month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/review-queue")
def queue(
    business_month: str = "",
    batch_id: str = "",
    latest_only: bool = True,
    limit: int = Query(default=1000, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    try:
        return list_review_queue(
            db,
            business_month,
            batch_id,
            latest_only,
            limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/review-queue/bulk-delete")
def delete_queue_rows(
    payload: dict,
    db: Session = Depends(get_db),
):
    try:
        return bulk_delete_review_queue(
            db,
            payload.get("ids") or [],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc



page_router = APIRouter(tags=["request-batch-compare-import-center"])

@page_router.get("/request-batch-compare-import-center", response_class=HTMLResponse)
def page():
    path = Path(__file__).parents[2] / "web" / "static" / "request_batch_compare_import_center.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))

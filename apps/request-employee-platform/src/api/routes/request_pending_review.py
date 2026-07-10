from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.request_pending_review_service import create_pending_review, get_pending_review, list_pending_reviews

router = APIRouter(prefix="/api/requests/pending-review", tags=["request-pending-review"])

@router.post("")
def create_record(payload: dict, db: Session = Depends(get_db)):
    try:
        return create_pending_review(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("")
def list_records(status: str = "", limit: int = Query(default=200, ge=1, le=1000), db: Session = Depends(get_db)):
    return list_pending_reviews(db, status=status, limit=limit)

@router.get("/{record_id}")
def get_record(record_id: str, db: Session = Depends(get_db)):
    record = get_pending_review(db, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Pending review record not found")
    return record

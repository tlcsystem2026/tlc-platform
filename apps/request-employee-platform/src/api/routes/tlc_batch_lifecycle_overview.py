from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_batch_lifecycle_overview_service import overview, timeline

router = APIRouter(prefix="/api/tlc-batches", tags=["tlc-batch-lifecycle-overview"])

@router.get("/{batch_id}/lifecycle-overview")
def get_overview(batch_id: str, db: Session = Depends(get_db)):
    try:
        return overview(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.get("/{batch_id}/lifecycle-timeline")
def get_timeline(
    batch_id: str,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        return timeline(db, batch_id, limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

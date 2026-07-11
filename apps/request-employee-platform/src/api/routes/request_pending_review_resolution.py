from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.request_pending_review_resolution_service import (
    list_review_history,
    resolve_pending_review,
)

router = APIRouter(prefix="/api/requests/pending-review", tags=["request-pending-review"])


@router.post("/{record_id}/resolve")
def resolve_record(record_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return resolve_pending_review(
            db,
            record_id,
            action=payload.get("action", ""),
            reviewed_by=payload.get("reviewed_by", ""),
            note=payload.get("note", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{record_id}/history")
def review_history(record_id: str, db: Session = Depends(get_db)):
    return list_review_history(db, record_id)

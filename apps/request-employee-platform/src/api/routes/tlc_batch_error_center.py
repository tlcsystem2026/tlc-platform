from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_batch_error_service import export_csv, list_errors, reopen_import, summary, sync_errors, update_error

router = APIRouter(prefix="/api/tlc-batches", tags=["tlc-batch-error-center"])

@router.post("/{batch_id}/errors/sync")
def sync(batch_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return sync_errors(db, batch_id, payload.get("operator", ""))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/{batch_id}/errors")
def errors(batch_id: str, db: Session = Depends(get_db)):
    try:
        return list_errors(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.get("/{batch_id}/errors/summary")
def error_summary(batch_id: str, db: Session = Depends(get_db)):
    try:
        return summary(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.put("/{batch_id}/errors/{error_id}")
def update(batch_id: str, error_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return update_error(db, batch_id, error_id, payload.get("status", ""), payload.get("operator", ""), payload.get("resolution_note", ""))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/{batch_id}/errors/reopen-import")
def reopen(batch_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return reopen_import(db, batch_id, payload.get("operator", ""))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/{batch_id}/errors/export.csv")
def download(batch_id: str, db: Session = Depends(get_db)):
    try:
        content = export_csv(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=content, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="batch_{batch_id}_compare_errors.csv"'})

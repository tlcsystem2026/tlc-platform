from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_batch_request_import_service import (
    list_files, list_logs, readiness, upload_file,
)

router = APIRouter(prefix="/api/tlc-batches", tags=["tlc-batch-request-import"])


@router.post("/{batch_id}/request-files")
async def upload(
    batch_id: str,
    request: Request,
    file_type: str,
    original_name: str,
    uploaded_by: str,
    db: Session = Depends(get_db),
):
    try:
        return upload_file(
            db, batch_id=batch_id, file_type=file_type,
            original_name=original_name,
            content_type=request.headers.get("content-type", ""),
            content=await request.body(), uploaded_by=uploaded_by,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{batch_id}/request-files")
def files(
    batch_id: str,
    include_inactive: bool = True,
    db: Session = Depends(get_db),
):
    try:
        return list_files(db, batch_id, include_inactive)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{batch_id}/request-import-readiness")
def ready(batch_id: str, db: Session = Depends(get_db)):
    try:
        return readiness(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{batch_id}/import-logs")
def logs(
    batch_id: str,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        return list_logs(db, batch_id, limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

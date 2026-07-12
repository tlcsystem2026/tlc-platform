
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_import_error_retry_service import (
    complete_retry,
    create_error,
    list_errors,
    list_retries,
    request_retry,
    summary,
    update_error,
)

router = APIRouter(prefix="/api/tlc-import-operations", tags=["tlc-import-error-retry"])


@router.post("/errors")
def create_import_error(payload: dict, db: Session = Depends(get_db)):
    try:
        return create_error(
            db,
            import_job_id=payload.get("import_job_id", ""),
            error_code=payload.get("error_code", ""),
            record_reference=payload.get("record_reference", ""),
            field_name=payload.get("field_name", ""),
            source_value=payload.get("source_value", ""),
            message=payload.get("message", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/errors")
def errors(
    import_job_id: str = "",
    batch_id: str = "",
    status: str = "",
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        return list_errors(
            db,
            import_job_id=import_job_id,
            batch_id=batch_id,
            status=status,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/errors/{error_id}")
def update_import_error(
    error_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    try:
        return update_error(
            db,
            error_id=error_id,
            status=payload.get("status", ""),
            operator=payload.get("operator", ""),
            resolution_note=payload.get("resolution_note", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/retries")
def create_retry(payload: dict, db: Session = Depends(get_db)):
    try:
        return request_retry(
            db,
            import_job_id=payload.get("import_job_id", ""),
            requested_by=payload.get("requested_by", ""),
            message=payload.get("message", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/retries/{retry_id}/complete")
def finish_retry(
    retry_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    try:
        return complete_retry(
            db,
            retry_id=retry_id,
            status=payload.get("status", ""),
            operator=payload.get("operator", ""),
            record_count=payload.get("record_count", 0),
            success_count=payload.get("success_count", 0),
            error_count=payload.get("error_count", 0),
            duplicate_count=payload.get("duplicate_count", 0),
            message=payload.get("message", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/retries")
def retries(
    import_job_id: str = "",
    batch_id: str = "",
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return list_retries(
        db,
        import_job_id=import_job_id,
        batch_id=batch_id,
        limit=limit,
    )


@router.get("/summary")
def get_summary(
    batch_id: str = "",
    db: Session = Depends(get_db),
):
    return summary(db, batch_id=batch_id)

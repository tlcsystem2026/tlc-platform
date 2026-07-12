from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_import_center_service import (
    ALLOWED_IMPORT_TYPES,
    ALLOWED_STATUSES,
    create_job,
    list_jobs,
    summary,
    update_job,
)


router = APIRouter(tags=["tlc-unified-import-center"])


@router.get("/api/tlc-import-jobs/types")
def import_types():
    return sorted(ALLOWED_IMPORT_TYPES)


@router.get("/api/tlc-import-jobs/statuses")
def import_statuses():
    return sorted(ALLOWED_STATUSES)


@router.post("/api/tlc-import-jobs")
def create(payload: dict, db: Session = Depends(get_db)):
    try:
        return create_job(
            db,
            batch_id=payload.get("batch_id", ""),
            import_type=payload.get("import_type", ""),
            source_name=payload.get("source_name", ""),
            source_reference=payload.get("source_reference", ""),
            created_by=payload.get("created_by", ""),
            message=payload.get("message", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/tlc-import-jobs")
def jobs(
    batch_id: str = "",
    import_type: str = "",
    status: str = "",
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        return list_jobs(
            db,
            batch_id=batch_id,
            import_type=import_type,
            status=status,
            limit=limit,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/tlc-import-jobs/{job_id}")
def update(job_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return update_job(
            db,
            job_id=job_id,
            status=payload.get("status", ""),
            operator=payload.get("operator", ""),
            record_count=payload.get("record_count"),
            success_count=payload.get("success_count"),
            error_count=payload.get("error_count"),
            duplicate_count=payload.get("duplicate_count"),
            message=payload.get("message"),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/tlc-import-jobs-summary")
def get_summary(
    batch_id: str = "",
    db: Session = Depends(get_db),
):
    try:
        return summary(db, batch_id=batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/import-center", response_class=HTMLResponse)
def import_center_page():
    page = Path(__file__).parents[2] / "web" / "static" / "import_center.html"
    return HTMLResponse(page.read_text(encoding="utf-8"))

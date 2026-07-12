from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_request_import_job_sync_service import sync_request_files_to_import_jobs

router = APIRouter(prefix="/api/tlc-import-jobs", tags=["tlc-request-import-job-sync"])

@router.post("/sync-request-files/{batch_id}")
def sync_request_files(batch_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return sync_request_files_to_import_jobs(db, batch_id=batch_id, operator=payload.get("operator", ""))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

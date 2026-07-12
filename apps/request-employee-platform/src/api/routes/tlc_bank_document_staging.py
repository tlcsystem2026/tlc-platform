
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_bank_document_staging_service import list_stages, stage_document, summary, update_stage

router = APIRouter(prefix="/api/tlc-import-jobs", tags=["tlc-bank-document-staging"])

@router.post("/stage-bank-document")
async def stage(
    request: Request, batch_id: str, document_type: str, original_name: str,
    source_reference: str, staged_by: str, bank_name: str = "",
    account_reference: str = "", db: Session = Depends(get_db),
):
    try:
        return stage_document(
            db, batch_id=batch_id, document_type=document_type,
            original_name=original_name, source_reference=source_reference,
            staged_by=staged_by, content=await request.body(),
            content_type=request.headers.get("content-type", ""),
            bank_name=bank_name, account_reference=account_reference,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.put("/bank-document-stages/{stage_id}")
def update(stage_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return update_stage(
            db, stage_id=stage_id, stage_status=payload.get("stage_status", ""),
            operator=payload.get("operator", ""),
            parser_contract=payload.get("parser_contract", ""),
            validation_message=payload.get("validation_message", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/bank-document-stages")
def stages(batch_id: str = "", limit: int = Query(default=500, ge=1, le=1000), db: Session = Depends(get_db)):
    return list_stages(db, batch_id=batch_id, limit=limit)

@router.get("/bank-document-stage-summary")
def get_summary(batch_id: str = "", db: Session = Depends(get_db)):
    return summary(db, batch_id=batch_id)

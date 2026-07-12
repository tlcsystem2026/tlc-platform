from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_bank_csv_import_job_service import register_bank_csv_import,list_links,summary
router=APIRouter(prefix="/api/tlc-import-jobs",tags=["tlc-bank-csv-import-job"])
@router.post("/register-bank-csv")
def register(payload:dict,db:Session=Depends(get_db)):
    try:return register_bank_csv_import(db,batch_id=payload.get("batch_id",""),bank_import_id=payload.get("bank_import_id",""),source_name=payload.get("source_name",""),source_reference=payload.get("source_reference",""),registered_by=payload.get("registered_by",""),bank_name=payload.get("bank_name",""),record_count=payload.get("record_count",0),success_count=payload.get("success_count",0),error_count=payload.get("error_count",0),duplicate_count=payload.get("duplicate_count",0),note=payload.get("note",""))
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
@router.get("/bank-csv-links")
def links(batch_id:str="",db:Session=Depends(get_db)):return list_links(db,batch_id)
@router.get("/bank-csv-summary")
def get_summary(batch_id:str="",db:Session=Depends(get_db)):return summary(db,batch_id)

from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_batch_compare_service import run_batch_compare,latest_batch_compare,list_batch_compares

router=APIRouter(prefix="/api/tlc-batches",tags=["tlc-batch-compare"])

@router.post("/{batch_id}/compare")
def compare(batch_id:str,payload:dict,db:Session=Depends(get_db)):
    try:return run_batch_compare(db,batch_id=batch_id,compared_by=payload.get("compared_by",""))
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.get("/{batch_id}/compare/latest")
def latest(batch_id:str,db:Session=Depends(get_db)):
    try:return latest_batch_compare(db,batch_id) or {}
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

@router.get("/{batch_id}/compare/history")
def history(batch_id:str,limit:int=Query(default=100,ge=1,le=1000),db:Session=Depends(get_db)):
    try:return list_batch_compares(db,batch_id,limit)
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

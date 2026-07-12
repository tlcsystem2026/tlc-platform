from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_batch_bank_center_service import create_link,list_links,summary
router=APIRouter(prefix="/api/tlc-batches",tags=["tlc-batch-bank-center"])

@router.post("/{batch_id}/bank/links")
def create(batch_id:str,payload:dict,db:Session=Depends(get_db)):
    try:return create_link(db,batch_id=batch_id,bank_transaction_id=payload.get("bank_transaction_id",""),
      bank_name=payload.get("bank_name",""),transaction_id=payload.get("transaction_id",""),
      transaction_date=payload.get("transaction_date",""),direction=payload.get("direction",""),
      amount=payload.get("amount","0"),counterparty=payload.get("counterparty",""),
      linked_by=payload.get("linked_by",""),note=payload.get("note",""))
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.get("/{batch_id}/bank/links")
def links(batch_id:str,db:Session=Depends(get_db)):
    try:return list_links(db,batch_id)
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

@router.get("/{batch_id}/bank/summary")
def get_summary(batch_id:str,db:Session=Depends(get_db)):
    try:return summary(db,batch_id)
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

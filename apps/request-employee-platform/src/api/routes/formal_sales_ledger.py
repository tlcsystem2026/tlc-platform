from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.formal_sales_ledger_service import get_sales_ledger_record,list_sales_ledger,post_approved_pending_review
router=APIRouter(prefix="/api/sales-ledger",tags=["sales-ledger"])

@router.post("/from-pending-review/{record_id}")
def post_record(record_id:str,db:Session=Depends(get_db)):
    try:return post_approved_pending_review(db,record_id)
    except LookupError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.get("")
def list_records(customer_id:str="",customer_name:str="",request_no:str="",status:str="",limit:int=Query(500,ge=1,le=1000),db:Session=Depends(get_db)):
    return list_sales_ledger(db,customer_id,customer_name,request_no,status,limit)

@router.get("/{ledger_id}")
def get_record(ledger_id:str,db:Session=Depends(get_db)):
    record=get_sales_ledger_record(db,ledger_id)
    if record is None: raise HTTPException(status_code=404,detail="Sales Ledger record not found")
    return record

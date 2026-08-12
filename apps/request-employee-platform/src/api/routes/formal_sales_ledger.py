from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.formal_sales_ledger_service import bulk_void_sales_ledger,cleanup_test_sales_ledger,get_sales_ledger_record,list_sales_ledger,post_approved_pending_review,sales_ledger_statistics
router=APIRouter(prefix="/api/sales-ledger",tags=["sales-ledger"])

@router.post("/from-pending-review/{record_id}")
def post_record(record_id:str,db:Session=Depends(get_db)):
    try:return post_approved_pending_review(db,record_id)
    except LookupError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.get("")
def list_records(customer_id:str="",customer_name:str="",request_no:str="",status:str="",keyword:str="",limit:int=Query(500,ge=1,le=1000),db:Session=Depends(get_db)):
    return list_sales_ledger(db,customer_id,customer_name,request_no,status,keyword,limit)

@router.post("/bulk-void")
def bulk_void(payload:dict,db:Session=Depends(get_db)):
    try:return bulk_void_sales_ledger(db,payload.get("ledger_ids",[]),payload.get("operator",""),payload.get("reason",""))
    except LookupError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.post("/admin/cleanup-test-data")
def cleanup_test_data(payload:dict,db:Session=Depends(get_db)):
    try:
        result=cleanup_test_sales_ledger(db,payload.get("ledger_ids",[]),payload.get("operator",""),payload.get("reason",""),payload.get("role",""),payload.get("confirmation",""))
        if result.get("status")=="blocked": raise HTTPException(status_code=409,detail=result)
        return result
    except PermissionError as exc: raise HTTPException(status_code=403,detail=str(exc)) from exc
    except LookupError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.get("/statistics/summary")
def statistics_summary(date_from:str="",date_to:str="",customer_id:str="",customer_name:str="",status:str="ACTIVE",db:Session=Depends(get_db)):
    return sales_ledger_statistics(db,date_from,date_to,customer_id,customer_name,status)

@router.get("/{ledger_id}")
def get_record(ledger_id:str,db:Session=Depends(get_db)):
    record=get_sales_ledger_record(db,ledger_id)
    if record is None: raise HTTPException(status_code=404,detail="Sales Ledger record not found")
    return record


from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_customer_reconciliation_confirmation_service import (
 create_confirmation,get_confirmation,list_audit,list_confirmations,update_confirmation)

router=APIRouter(prefix="/api/tlc-customer-reconciliation-confirmations",tags=["tlc-customer-reconciliation-confirmation"])

@router.post("")
def create(payload:dict,db:Session=Depends(get_db)):
    try:return create_confirmation(db,snapshot_id=payload.get("snapshot_id",""),operator=payload.get("operator",""),note=payload.get("note",""))
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.put("/{confirmation_id}")
def update(confirmation_id:str,payload:dict,db:Session=Depends(get_db)):
    try:return update_confirmation(db,confirmation_id=confirmation_id,status=payload.get("status",""),
      operator=payload.get("operator",""),confirmed_sales_total=payload.get("confirmed_sales_total",""),
      confirmed_payment_total=payload.get("confirmed_payment_total",""),
      correction_reason=payload.get("correction_reason",""),note=payload.get("note",""))
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.get("")
def list_items(customer_id:str="",status:str="",limit:int=Query(default=200,ge=1,le=1000),db:Session=Depends(get_db)):
    try:return list_confirmations(db,customer_id=customer_id,status=status,limit=limit)
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.get("/audit")
def audit(confirmation_id:str="",customer_id:str="",limit:int=Query(default=500,ge=1,le=2000),db:Session=Depends(get_db)):
    return list_audit(db,confirmation_id=confirmation_id,customer_id=customer_id,limit=limit)

@router.get("/{confirmation_id}")
def detail(confirmation_id:str,db:Session=Depends(get_db)):
    try:return get_confirmation(db,confirmation_id)
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e

page_router=APIRouter(tags=["tlc-customer-reconciliation-confirmation-center"])
@page_router.get("/customer-reconciliation-confirmation-center",response_class=HTMLResponse)
def page():
    p=Path(__file__).parents[2]/"web"/"static"/"customer_reconciliation_confirmation_center.html"
    return HTMLResponse(p.read_text(encoding="utf-8"))


from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_customer_reconciliation_case_service import (
    apply_correction,cancel,confirm,create_case,list_audit,list_cases,request_correction
)

router=APIRouter(prefix="/api/tlc-customer-reconciliation-cases",tags=["tlc-customer-reconciliation-case"])

@router.post("")
def create(payload:dict,db:Session=Depends(get_db)):
    try:return create_case(db,snapshot_id=payload.get("snapshot_id",""),operator=payload.get("operator",""))
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.put("/{rid}/confirm")
def do_confirm(rid:str,payload:dict,db:Session=Depends(get_db)):
    try:return confirm(db,rid=rid,operator=payload.get("operator",""),note=payload.get("note",""))
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.put("/{rid}/request-correction")
def request_fix(rid:str,payload:dict,db:Session=Depends(get_db)):
    try:return request_correction(db,rid=rid,operator=payload.get("operator",""),reason=payload.get("reason",""))
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.put("/{rid}/apply-correction")
def apply_fix(rid:str,payload:dict,db:Session=Depends(get_db)):
    try:return apply_correction(db,rid=rid,operator=payload.get("operator",""),
      sales=payload.get("adjusted_sales_total","0"),payment=payload.get("adjusted_payment_total","0"),
      note=payload.get("note",""))
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.put("/{rid}/cancel")
def do_cancel(rid:str,payload:dict,db:Session=Depends(get_db)):
    try:return cancel(db,rid=rid,operator=payload.get("operator",""),note=payload.get("note",""))
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.get("")
def items(customer_id:str="",status:str="",limit:int=Query(default=500,ge=1,le=1000),db:Session=Depends(get_db)):
    try:return list_cases(db,customer_id=customer_id,status=status,limit=limit)
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.get("/{rid}/audit")
def audits(rid:str,limit:int=Query(default=1000,ge=1,le=2000),db:Session=Depends(get_db)):
    return list_audit(db,rid=rid,limit=limit)

page_router=APIRouter(tags=["tlc-customer-reconciliation-confirmation-center"])
@page_router.get("/customer-reconciliation-confirmation-center",response_class=HTMLResponse)
def page():
    p=Path(__file__).parents[2]/"web"/"static"/"customer_reconciliation_confirmation_center.html"
    return HTMLResponse(p.read_text(encoding="utf-8"))

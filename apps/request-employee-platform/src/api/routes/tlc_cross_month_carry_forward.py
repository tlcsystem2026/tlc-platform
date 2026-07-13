
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_cross_month_carry_forward_service import (
    auto_generate_from_month,control_view,create_carry_forward,
    list_carry_forwards,update_carry_forward
)
router=APIRouter(prefix="/api/tlc-monthly-close/carry-forwards",tags=["tlc-cross-month-carry-forward"])

@router.post("")
def create(payload:dict,db:Session=Depends(get_db)):
    try:return create_carry_forward(db,source_month=payload.get("source_month",""),
      target_month=payload.get("target_month",""),category=payload.get("category",""),
      title=payload.get("title",""),created_by=payload.get("created_by",""),
      source_batch_id=payload.get("source_batch_id",""),reference_id=payload.get("reference_id",""),
      amount=payload.get("amount","0"),currency=payload.get("currency",""),reason=payload.get("reason",""))
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.get("")
def list_items(source_month:str="",target_month:str="",status:str="",
               limit:int=Query(default=500,ge=1,le=1000),db:Session=Depends(get_db)):
    try:return list_carry_forwards(db,source_month=source_month,target_month=target_month,status=status,limit=limit)
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.put("/{item_id}")
def update(item_id:str,payload:dict,db:Session=Depends(get_db)):
    try:return update_carry_forward(db,item_id=item_id,status=payload.get("status",""),
      operator=payload.get("operator",""),resolution_note=payload.get("resolution_note",""))
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.post("/auto-generate")
def auto_generate(payload:dict,db:Session=Depends(get_db)):
    try:return auto_generate_from_month(db,source_month=payload.get("source_month",""),
      target_month=payload.get("target_month",""),operator=payload.get("operator",""))
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.get("/control-view/{business_month}")
def view(business_month:str,db:Session=Depends(get_db)):
    return control_view(db,business_month)

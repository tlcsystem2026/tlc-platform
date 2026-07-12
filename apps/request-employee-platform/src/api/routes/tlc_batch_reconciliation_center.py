from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_batch_reconciliation_service import create_link,list_links,summary,finish_batch
router=APIRouter(prefix='/api/tlc-batches',tags=['tlc-batch-reconciliation-center'])
@router.post('/{batch_id}/reconciliation/links')
def create(batch_id:str,payload:dict,db:Session=Depends(get_db)):
 try:return create_link(db,batch_id=batch_id,reconciliation_id=payload.get('reconciliation_id',''),customer_id=payload.get('customer_id',''),customer_name=payload.get('customer_name',''),period_sales_total=payload.get('period_sales_total','0'),period_payment_total=payload.get('period_payment_total','0'),closing_outstanding=payload.get('closing_outstanding','0'),reconciliation_status=payload.get('reconciliation_status',''),confirmed_by=payload.get('confirmed_by',''),confirmed_at=payload.get('confirmed_at',''),linked_by=payload.get('linked_by',''),note=payload.get('note',''))
 except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
 except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e
@router.get('/{batch_id}/reconciliation/links')
def links(batch_id:str,db:Session=Depends(get_db)):
 try:return list_links(db,batch_id)
 except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
@router.get('/{batch_id}/reconciliation/summary')
def get_summary(batch_id:str,db:Session=Depends(get_db)):
 try:return summary(db,batch_id)
 except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
@router.post('/{batch_id}/reconciliation/finish')
def finish(batch_id:str,payload:dict,db:Session=Depends(get_db)):
 try:return finish_batch(db,batch_id=batch_id,operator=payload.get('operator',''),message=payload.get('message',''))
 except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
 except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

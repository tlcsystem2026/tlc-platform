from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_batch_review_service import get_review_payload,create_link,list_links,update_link

router=APIRouter(prefix="/api/tlc-batches",tags=["tlc-batch-review-center"])

@router.get("/{batch_id}/review/payload")
def payload(batch_id:str,db:Session=Depends(get_db)):
    try:return get_review_payload(db,batch_id)
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.post("/{batch_id}/review/links")
def create(batch_id:str,payload:dict,db:Session=Depends(get_db)):
    try:return create_link(db,batch_id=batch_id,pending_review_id=payload.get("pending_review_id",""),
      linked_by=payload.get("linked_by",""),note=payload.get("note",""))
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

@router.get("/{batch_id}/review/links")
def links(batch_id:str,db:Session=Depends(get_db)):
    try:return list_links(db,batch_id)
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc

@router.put("/{batch_id}/review/links/{link_id}")
def update(batch_id:str,link_id:str,payload:dict,db:Session=Depends(get_db)):
    try:return update_link(db,batch_id=batch_id,link_id=link_id,
      review_status=payload.get("review_status",""),operator=payload.get("operator",""),
      note=payload.get("note",""))
    except LookupError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

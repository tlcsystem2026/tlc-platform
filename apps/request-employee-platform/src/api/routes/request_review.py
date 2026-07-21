
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.request_review_service import list_reviews,get_review,update_review,update_reviews_batch,wait_review_count

router=APIRouter(prefix="/api/tlc-request-reviews",tags=["tlc-request-reviews"])

@router.get("")
def items(business_month:str="",batch_id:str="",latest_only:bool=True,review_status:str="WAIT_REVIEW",compare_status:str="",customer_match_status:str="",keyword:str="",limit:int=Query(500,ge=1,le=2000),db:Session=Depends(get_db)):
    return list_reviews(db,business_month,batch_id,latest_only,review_status,compare_status,customer_match_status,keyword,limit)

@router.get("/wait-count")
def count(db:Session=Depends(get_db)):
    return {"count":wait_review_count(db)}

@router.get("/{review_id}")
def detail(review_id:str,db:Session=Depends(get_db)):
    try:return get_review(db,review_id)
    except LookupError as exc:raise HTTPException(404,str(exc)) from exc

@router.put("/batch")
def decide_batch(payload:dict,db:Session=Depends(get_db)):
    try:
        return update_reviews_batch(db,payload.get("review_ids",[]),payload.get("review_status",""),payload.get("operator",""),payload.get("comment",""),bool(payload.get("forced",False)))
    except LookupError as exc:raise HTTPException(404,str(exc)) from exc
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc

@router.put("/{review_id}")
def decide(review_id:str,payload:dict,db:Session=Depends(get_db)):
    try:
        return update_review(db,review_id,payload.get("review_status",""),payload.get("operator",""),payload.get("comment",""),bool(payload.get("forced",False)))
    except LookupError as exc:raise HTTPException(404,str(exc)) from exc
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc

page_router=APIRouter(tags=["request-review-center"])

@page_router.get("/request-review-center",response_class=HTMLResponse)
def page():
    p=Path(__file__).parents[2]/"web"/"static"/"request_review_center.html"
    return HTMLResponse(p.read_text(encoding="utf-8"))

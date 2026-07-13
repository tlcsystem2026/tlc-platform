from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_customer_recommended_matching_service import (
    decide_recommendation, generate_recommendations,
    list_recommendation_audit, list_recommendations,
)

router=APIRouter(prefix="/api/tlc-customer-recommended-matching",tags=["tlc-customer-recommended-matching"])

@router.post("/generate")
def generate(payload:dict,db:Session=Depends(get_db)):
    try:return generate_recommendations(db,reconciliation_id=payload.get("reconciliation_id",""),operator=payload.get("operator",""),minimum_score=payload.get("minimum_score",70))
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.put("/{recommendation_id}/status")
def update_status(recommendation_id:str,payload:dict,db:Session=Depends(get_db)):
    try:return decide_recommendation(db,recommendation_id=recommendation_id,status=payload.get("status",""),operator=payload.get("operator",""),note=payload.get("note",""))
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.get("")
def items(reconciliation_id:str="",status:str="",limit:int=Query(default=1000,ge=1,le=2000),db:Session=Depends(get_db)):
    try:return list_recommendations(db,reconciliation_id=reconciliation_id,status=status,limit=limit)
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e

@router.get("/{recommendation_id}/audit")
def audit(recommendation_id:str,limit:int=Query(default=1000,ge=1,le=2000),db:Session=Depends(get_db)):
    return list_recommendation_audit(db,recommendation_id=recommendation_id,limit=limit)

page_router=APIRouter(tags=["tlc-customer-recommended-matching-center"])
@page_router.get("/customer-recommended-matching-center",response_class=HTMLResponse)
def page():
    p=Path(__file__).parents[2]/"web"/"static"/"customer_recommended_matching_center.html"
    return HTMLResponse(p.read_text(encoding="utf-8"))

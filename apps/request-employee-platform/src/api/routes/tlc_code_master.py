from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_code_master_service import list_categories,list_values,save_category,save_value
router=APIRouter(tags=["tlc-code-master"])
@router.get("/api/tlc-codes/categories")
def categories(include_inactive:bool=True,db:Session=Depends(get_db)):return list_categories(db,include_inactive)
@router.post("/api/tlc-codes/categories")
def category_save(payload:dict,db:Session=Depends(get_db)):
    try:return save_category(db,payload)
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e
@router.get("/api/tlc-codes/values")
def values(category_code:str,db:Session=Depends(get_db)):return list_values(db,category_code)
@router.post("/api/tlc-codes/values")
def value_save(payload:dict,db:Session=Depends(get_db)):
    try:return save_value(db,payload)
    except LookupError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=400,detail=str(e)) from e
@router.get("/tlc-code-master",response_class=HTMLResponse)
def page():return HTMLResponse((Path(__file__).parents[2]/"web"/"static"/"tlc_code_master.html").read_text(encoding="utf-8"))

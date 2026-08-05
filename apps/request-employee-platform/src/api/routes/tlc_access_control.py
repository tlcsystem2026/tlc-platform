from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_access_control_service import assign_roles,audit_rows,overview,save_department,save_permissions,save_user
router=APIRouter(tags=["tlc-access-control"])
@router.get("/access-control-center",response_class=HTMLResponse)
def page():return HTMLResponse((Path(__file__).parents[2]/"web/static/access_control_center.html").read_text(encoding="utf-8"))
@router.get("/api/access-control/overview")
def get_overview(db:Session=Depends(get_db)):
 result=overview(db);result["roles"]=[x for x in result["roles"] if x["role_code"]!="SUPER_ADMIN"];return result
@router.post("/api/access-control/departments")
def department(payload:dict,db:Session=Depends(get_db)):
 try:return save_department(db,payload)
 except ValueError as e:raise HTTPException(400,detail=str(e)) from e
@router.post("/api/access-control/users")
def user(payload:dict,db:Session=Depends(get_db)):
 try:return save_user(db,payload)
 except ValueError as e:raise HTTPException(400,detail=str(e)) from e
@router.put("/api/access-control/users/{user_id}/roles")
def roles(user_id:str,payload:dict,db:Session=Depends(get_db)):
 try:return assign_roles(db,user_id,payload.get("role_codes",[]),payload.get("actor",""))
 except ValueError as e:raise HTTPException(400,detail=str(e)) from e
@router.put("/api/access-control/roles/{role_code}/permissions")
def permissions(role_code:str,payload:dict,db:Session=Depends(get_db)):
 try:return save_permissions(db,role_code,payload.get("items",[]),payload.get("actor",""))
 except ValueError as e:raise HTTPException(400,detail=str(e)) from e
@router.get("/api/access-control/audit")
def permission_audit(limit:int=200,db:Session=Depends(get_db)):return audit_rows(db,limit)

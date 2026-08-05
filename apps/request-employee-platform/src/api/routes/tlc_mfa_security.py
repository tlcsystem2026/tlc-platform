from pathlib import Path
import os
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_authentication_service import COOKIE_NAME,current_session
from src.services.tlc_mfa_security_service import create_step_up,disable_mfa,enable_mfa,list_sessions,mfa_status,revoke_session,security_audit,setup_mfa

router=APIRouter(tags=["tlc-mfa-security"])
STEP_COOKIE="tlc_step_up"
def session(request,db):
 value=current_session(db,request.cookies.get(COOKIE_NAME,""),touch=False)
 if not value:raise HTTPException(401,"请先登录")
 return value
def admin(db,user):return bool(db.execute(text("SELECT 1 FROM tlc_user_role WHERE user_id=:u AND role_code IN ('SUPER_ADMIN','SECURITY_ADMIN') LIMIT 1"),{"u":user}).first())

@router.get("/security-center",response_class=HTMLResponse)
def page():return HTMLResponse((Path(__file__).parents[2]/"web/static/security_center.html").read_text(encoding="utf-8"))
@router.get("/api/security/overview")
def overview(request:Request,db:Session=Depends(get_db)):
 s=session(request,db);is_admin=admin(db,s["user_id"]);return {"mfa":mfa_status(db,s["user_id"]),"sessions":list_sessions(db,s["user_id"],is_admin),"audit":security_audit(db) if is_admin else [],"is_security_admin":is_admin,"current_session_id":s["id"]}
@router.post("/api/security/mfa/setup")
def mfa_setup(request:Request,db:Session=Depends(get_db)):
 s=session(request,db)
 try:return setup_mfa(db,s["user_id"],s["login_id"])
 except ValueError as exc:raise HTTPException(400,str(exc)) from exc
@router.post("/api/security/mfa/enable")
def mfa_enable(payload:dict,request:Request,db:Session=Depends(get_db)):
 try:return enable_mfa(db,session(request,db)["user_id"],str(payload.get("code")or""),request.client.host if request.client else "")
 except ValueError as exc:raise HTTPException(400,str(exc)) from exc
@router.post("/api/security/mfa/disable")
def mfa_disable(payload:dict,request:Request,db:Session=Depends(get_db)):
 try:return disable_mfa(db,session(request,db)["user_id"],str(payload.get("code")or""),request.client.host if request.client else "")
 except ValueError as exc:raise HTTPException(400,str(exc)) from exc
@router.post("/api/security/step-up")
def step_up(payload:dict,request:Request,response:Response,db:Session=Depends(get_db)):
 s=session(request,db)
 try:result=create_step_up(db,s["user_id"],str(payload.get("password")or""),str(payload.get("code")or""),request.client.host if request.client else "")
 except PermissionError as exc:raise HTTPException(401,str(exc)) from exc
 response.set_cookie(STEP_COOKIE,result.pop("token"),httponly=True,samesite="strict",secure=os.getenv("TLC_SESSION_COOKIE_SECURE","0")=="1",max_age=300,path="/");return result
@router.post("/api/security/sessions/{session_id}/revoke")
def revoke(session_id:str,request:Request,db:Session=Depends(get_db)):
 s=session(request,db)
 try:return revoke_session(db,session_id,s["user_id"],admin(db,s["user_id"]))
 except LookupError as exc:raise HTTPException(404,str(exc)) from exc
 except PermissionError as exc:raise HTTPException(403,str(exc)) from exc

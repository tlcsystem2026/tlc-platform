from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_authentication_service import COOKIE_NAME,current_session
from src.services.tlc_security_ip_control_service import cancel_enforcement,confirm_enforcement,delete_proxy,delete_rule,enforcement_status,monitor_request,overview,save_proxy,save_rule,start_enforcement_test

router=APIRouter(tags=["tlc-security-ip-control"])

def _session(request:Request,db:Session)->dict:
    value=current_session(db,request.cookies.get(COOKIE_NAME,""),touch=False)
    if not value:raise HTTPException(401,"请先登录")
    return value

@router.get("/security-ip-control-center",response_class=HTMLResponse)
def page():return HTMLResponse((Path(__file__).parents[2]/"web/static/security_ip_control_center.html").read_text(encoding="utf-8"))

@router.get("/api/security-ip-control/overview")
def get_overview(request:Request,db:Session=Depends(get_db)):
    result=overview(db);result["current_access"]=monitor_request(db,_session(request,db),"GET","/api/security-ip-control/overview",request.client.host if request.client else "",request.headers.get("x-forwarded-for",""),record=False);return result

@router.post("/api/security-ip-control/rules")
def rule_save(payload:dict,db:Session=Depends(get_db)):
    try:return save_rule(db,payload)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc

@router.delete("/api/security-ip-control/rules/{record_id}")
def rule_delete(record_id:str,db:Session=Depends(get_db)):
    try:return delete_rule(db,record_id)
    except LookupError as exc:raise HTTPException(404,str(exc)) from exc

@router.post("/api/security-ip-control/trusted-proxies")
def proxy_save(payload:dict,db:Session=Depends(get_db)):
    try:return save_proxy(db,payload)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc

@router.delete("/api/security-ip-control/trusted-proxies/{record_id}")
def proxy_delete(record_id:str,db:Session=Depends(get_db)):
    try:return delete_proxy(db,record_id)
    except LookupError as exc:raise HTTPException(404,str(exc)) from exc

@router.get("/api/security-ip-control/enforcement")
def enforcement(request:Request,db:Session=Depends(get_db)):
    _session(request,db);return enforcement_status(db)

@router.post("/api/security-ip-control/enforcement/test")
def enforcement_test(payload:dict,request:Request,db:Session=Depends(get_db)):
    try:return start_enforcement_test(db,_session(request,db),request.client.host if request.client else "",request.headers.get("x-forwarded-for",""),str(payload.get("confirmation")or""))
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc

@router.post("/api/security-ip-control/enforcement/confirm")
def enforcement_confirm(payload:dict,request:Request,db:Session=Depends(get_db)):
    try:return confirm_enforcement(db,_session(request,db),request.client.host if request.client else "",request.headers.get("x-forwarded-for",""),str(payload.get("test_id")or""),str(payload.get("confirmation")or""))
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc

@router.post("/api/security-ip-control/enforcement/cancel")
def enforcement_cancel(payload:dict,request:Request,db:Session=Depends(get_db)):
    try:return cancel_enforcement(db,_session(request,db),request.client.host if request.client else "",str(payload.get("confirmation")or""))
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc

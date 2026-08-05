from pathlib import Path
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db.session import SessionLocal, get_db
from src.services.tlc_authentication_service import COOKIE_NAME, audit_rows, bootstrap, change_password, current_session, login, logout
from src.services.tlc_super_admin_service import internal_ip_allowed
from src.services.tlc_api_permission_service import authorize, dashboard_permission_script, visible_modules  # TLC_BUSINESS_PERMISSION_COVERAGE_R1
from src.services.tlc_security_ip_control_service import enforce_request  # TLC_SECURITY_IP_ENFORCEMENT_R2  # TLC_API_PERMISSION_ENFORCEMENT_R1


router = APIRouter(tags=["tlc-authentication"])
PUBLIC_PATHS = {"/login", "/api/auth/login", "/api/auth/bootstrap", "/health", "/docs", "/openapi.json", "/favicon.ico"}


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _session(request: Request, db: Session, touch: bool = True) -> dict:
    result = current_session(db, request.cookies.get(COOKIE_NAME, ""), touch=touch)
    if not result:raise HTTPException(status_code=401, detail="请先登录")
    return result


@router.get("/login", response_class=HTMLResponse)
def login_page():return HTMLResponse((Path(__file__).parents[2]/"web/static/login.html").read_text(encoding="utf-8"))


@router.get("/change-password", response_class=HTMLResponse)
def password_page():return HTMLResponse((Path(__file__).parents[2]/"web/static/change_password.html").read_text(encoding="utf-8"))


@router.get("/my-profile", response_class=HTMLResponse)
def profile_page():return HTMLResponse((Path(__file__).parents[2]/"web/static/my_profile.html").read_text(encoding="utf-8"))


@router.post("/api/auth/bootstrap")
def auth_bootstrap(payload: dict, request: Request, db: Session = Depends(get_db)):
    if not internal_ip_allowed(_ip(request)):raise HTTPException(403, "初始超级管理员只能从内部IP设置")
    try:return bootstrap(db,str(payload.get("employee_no")or""),str(payload.get("login_id")or""),str(payload.get("name_zh")or""),str(payload.get("password")or""),_ip(request))
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc


@router.post("/api/auth/login")
def auth_login(payload: dict, request: Request, response: Response, db: Session = Depends(get_db)):
    try:result=login(db,str(payload.get("login_id")or""),str(payload.get("password")or""),_ip(request),request.headers.get("user-agent", ""))
    except PermissionError as exc:raise HTTPException(401,str(exc)) from exc
    response.set_cookie(COOKIE_NAME,result.pop("token"),httponly=True,samesite="strict",secure=os.getenv("TLC_SESSION_COOKIE_SECURE","0")=="1",max_age=8*60*60,path="/")
    return result


@router.post("/api/auth/logout")
def auth_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    logout(db,request.cookies.get(COOKIE_NAME,""),_ip(request));response.delete_cookie(COOKIE_NAME,path="/");return {"logged_out":True}


@router.get("/api/auth/me")
def auth_me(request: Request, db: Session = Depends(get_db)):return _session(request,db)


@router.post("/api/auth/change-password")
def auth_change_password(payload:dict,request:Request,db:Session=Depends(get_db)):
    try:return change_password(db,request.cookies.get(COOKIE_NAME,""),str(payload.get("current_password")or""),str(payload.get("new_password")or""),_ip(request))
    except PermissionError as exc:raise HTTPException(401,str(exc)) from exc
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc


@router.get("/api/auth/audit")
def auth_audit(request:Request,limit:int=200,db:Session=Depends(get_db)):
    session=_session(request,db);roles={str(x[0]) for x in db.execute(text("SELECT role_code FROM tlc_user_role WHERE user_id=:user"),{"user":session["user_id"]}).all()}
    if "SUPER_ADMIN" not in roles and "SECURITY_ADMIN" not in roles:raise HTTPException(403,"需要安全管理权限")
    return audit_rows(db,limit)


@router.get("/api/auth/navigation")
def auth_navigation(request: Request, db: Session = Depends(get_db)):
    return visible_modules(db, _session(request, db, touch=False))


def install_authentication(app) -> None:
    @app.middleware("http")
    async def authentication_middleware(request: Request, call_next):
        if os.getenv("PYTEST_CURRENT_TEST") and os.getenv("TLC_AUTH_TEST_FORCE", "0") != "1":return await call_next(request)
        if os.getenv("TLC_AUTH_ENFORCEMENT_ENABLED", "1") != "1":return await call_next(request)
        if request.url.path in PUBLIC_PATHS:
            public_db=SessionLocal()
            try:public_access=enforce_request(public_db,{},request.method,request.url.path,_ip(request),request.headers.get("x-forwarded-for",""))
            finally:public_db.close()
            if public_access.get("blocked"):
                return JSONResponse({"detail":"IP access denied","decision":public_access.get("decision")},status_code=403)
            return await call_next(request)
        db=SessionLocal()
        try:session=current_session(db,request.cookies.get(COOKIE_NAME,""))
        finally:db.close()
        if not session:
            if request.url.path.startswith("/api/"):return JSONResponse({"detail":"请先登录"},status_code=401)
            return RedirectResponse("/login?next="+request.url.path,status_code=303)
        if session.get("must_change_password") and request.url.path not in {"/change-password","/api/auth/change-password","/api/auth/logout","/api/auth/me"}:
            if request.url.path.startswith("/api/"):return JSONResponse({"detail":"首次登录必须修改密码"},status_code=403)
            return RedirectResponse("/change-password",status_code=303)
        request.state.auth_user=session
        permission_db=SessionLocal()
        try:
            ip_access=enforce_request(permission_db,session,request.method,request.url.path,_ip(request),request.headers.get("x-forwarded-for",""))
            decision=authorize(permission_db,session,request.method,request.url.path)
        finally:permission_db.close()
        if ip_access.get("blocked"):
            return JSONResponse({"detail":"IP access denied","decision":ip_access.get("decision")},status_code=403)
        if decision.get("required") and not decision.get("allowed"):
            return JSONResponse({"detail":"Permission denied","module_code":decision["module_code"],"action_code":decision["action_code"]},status_code=403)
        request.state.permission_scope=decision.get("data_scope","")
        response=await call_next(request)
        if request.url.path=="/dashboard" and "text/html" in response.headers.get("content-type",""):
            body=b"".join([chunk async for chunk in response.body_iterator])
            html=body.decode("utf-8")
            html=html.replace("</body>",dashboard_permission_script()+"</body>")
            headers=dict(response.headers);headers.pop("content-length",None)
            return Response(content=html,status_code=response.status_code,headers=headers,media_type="text/html")
        return response

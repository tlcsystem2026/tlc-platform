from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_super_admin_service import grant, internal_ip_allowed, overview, revoke


router = APIRouter(tags=["tlc-super-admin"])


def require_internal(request: Request) -> None:
    client_ip = request.client.host if request.client else ""
    if not internal_ip_allowed(client_ip):
        raise HTTPException(status_code=403, detail="超级管理员设置仅允许从内部IP访问")


@router.get("/super-admin-management", response_class=HTMLResponse)
def page(request: Request):
    require_internal(request)
    return HTMLResponse((Path(__file__).parents[2] / "web/static/super_admin_management.html").read_text(encoding="utf-8"))


@router.get("/api/super-admin/overview")
def get_overview(request: Request, db: Session = Depends(get_db)):
    require_internal(request)
    return overview(db)


@router.post("/api/super-admin/grant")
def grant_super_admin(payload: dict, request: Request, db: Session = Depends(get_db)):
    require_internal(request)
    try:
        return grant(db, str(payload.get("target_user_id") or ""), str(payload.get("actor_user_id") or ""), str(payload.get("reason") or ""), str(payload.get("confirmation") or ""))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/super-admin/revoke")
def revoke_super_admin(payload: dict, request: Request, db: Session = Depends(get_db)):
    require_internal(request)
    try:
        return revoke(db, str(payload.get("target_user_id") or ""), str(payload.get("actor_user_id") or ""), str(payload.get("reason") or ""), str(payload.get("confirmation") or ""))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

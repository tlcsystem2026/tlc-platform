from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_customer_identity_audit_service import impact_preview, resolve_conflict, scan_conflicts

router = APIRouter(tags=["customer-identity-audit"])

@router.get("/customer-identity-audit-center", response_class=HTMLResponse)
def page():
    return HTMLResponse((Path(__file__).parents[2]/"web/static/customer_identity_audit_center.html").read_text(encoding="utf-8"))

@router.get("/api/customer-identity-audit/scan")
def scan(db: Session=Depends(get_db)):
    return scan_conflicts(db)

@router.get("/api/customer-identity-audit/{identity_id}/impact")
def impact(identity_id: str, db: Session=Depends(get_db)):
    try: return impact_preview(db, identity_id)
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc

@router.post("/api/customer-identity-audit/{identity_id}/resolve")
def resolve(identity_id: str, payload: dict, db: Session=Depends(get_db)):
    try:
        return resolve_conflict(db, identity_id, str(payload.get("action") or ""),
          str(payload.get("actor") or ""), str(payload.get("reason") or ""),
          str(payload.get("target_customer_id") or ""))
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc

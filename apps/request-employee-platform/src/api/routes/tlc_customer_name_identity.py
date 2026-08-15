from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_customer_name_identity_service import list_names, register_name, deactivate_name

router = APIRouter(tags=["customer-name-identity"])

@router.get("/customer-name-identity-center", response_class=HTMLResponse)
def page():
    return HTMLResponse((Path(__file__).parents[2] / "web/static/customer_name_identity_center.html").read_text(encoding="utf-8"))

@router.get("/api/customer-name-identities")
def items(query: str = "", customer_id: str = "", name_type: str = "", language_code: str = "",
          include_inactive: bool = False, db: Session = Depends(get_db)):
    return list_names(db, query, customer_id, name_type, language_code, include_inactive)

@router.post("/api/customer-name-identities")
def create(payload: dict, db: Session = Depends(get_db)):
    try:
        return register_name(db, customer_record_id=str(payload.get("customer_record_id") or ""),
          customer_id=str(payload.get("customer_id") or ""), name_value=str(payload.get("name_value") or ""),
          name_type=str(payload.get("name_type") or ""), language_code=str(payload.get("language_code") or ""),
          source_system="MANUAL", actor=str(payload.get("actor") or ""))
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc

@router.post("/api/customer-name-identities/{identity_id}/deactivate")
def deactivate(identity_id: str, payload: dict, db: Session = Depends(get_db)):
    try: return deactivate_name(db, identity_id, str(payload.get("actor") or ""), str(payload.get("reason") or ""))
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc

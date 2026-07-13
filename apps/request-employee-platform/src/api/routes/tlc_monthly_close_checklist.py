
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.services.tlc_monthly_close_checklist_service import (
    control_view, initialize_checklist, signoff, update_checklist_item
)

router = APIRouter(prefix="/api/tlc-monthly-close", tags=["tlc-monthly-close-checklist"])

@router.post("/{business_month}/checklist/initialize")
def initialize(business_month: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return initialize_checklist(
            db, business_month=business_month, operator=payload.get("operator", "")
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.put("/checklist/items/{item_id}")
def update_item(item_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return update_checklist_item(
            db, item_id=item_id, status=payload.get("status", ""),
            operator=payload.get("operator", ""), note=payload.get("note", "")
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.put("/{business_month}/signoff")
def update_signoff(business_month: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return signoff(
            db, business_month=business_month, status=payload.get("status", ""),
            operator=payload.get("operator", ""), note=payload.get("note", "")
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/{business_month}/control-view")
def view(business_month: str, db: Session = Depends(get_db)):
    return control_view(db, business_month)

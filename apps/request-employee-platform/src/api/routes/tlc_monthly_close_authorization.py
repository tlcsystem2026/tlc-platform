
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_monthly_close_authorization_service import (
    control_view,
    decide_authorization,
    execute_authorization,
    list_audit,
    list_authorizations,
    request_authorization,
)


router = APIRouter(
    prefix="/api/tlc-monthly-close/authorizations",
    tags=["tlc-monthly-close-authorization"],
)


@router.post("")
def request(payload: dict, db: Session = Depends(get_db)):
    try:
        return request_authorization(
            db,
            business_month=payload.get("business_month", ""),
            action=payload.get("action", ""),
            requested_by=payload.get("requested_by", ""),
            reason=payload.get("reason", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{authorization_id}/decision")
def decide(
    authorization_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    try:
        return decide_authorization(
            db,
            authorization_id=authorization_id,
            decision=payload.get("decision", ""),
            approver=payload.get("approver", ""),
            note=payload.get("note", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{authorization_id}/execute")
def execute(
    authorization_id: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    try:
        return execute_authorization(
            db,
            authorization_id=authorization_id,
            operator=payload.get("operator", ""),
            note=payload.get("note", ""),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_items(
    business_month: str = "",
    action: str = "",
    decision: str = "",
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    try:
        return list_authorizations(
            db,
            business_month=business_month,
            action=action,
            decision=decision,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit")
def audit(
    business_month: str = "",
    authorization_id: str = "",
    limit: int = Query(default=1000, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    return list_audit(
        db,
        business_month=business_month,
        authorization_id=authorization_id,
        limit=limit,
    )


@router.get("/control-view/{business_month}")
def view(
    business_month: str,
    db: Session = Depends(get_db),
):
    return control_view(db, business_month)

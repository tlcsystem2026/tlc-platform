import csv
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_customer_candidate_service import (
    bulk_resolve_candidates,
    export_csv,
    import_csv,
    latest_batch,
    list_candidates,
    resolve_candidate,
    run_extraction,
)

router = APIRouter(tags=["tlc-customer-candidate"])


@router.get("/customer-import-candidate-center", response_class=HTMLResponse)
def page():
    path = Path(__file__).parents[2] / "web" / "static" / "customer_import_candidate_center.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.post("/api/customer-candidates/batches")
def run_batch(payload: dict, db: Session = Depends(get_db)):
    try:
        return run_extraction(db, str(payload.get("business_month") or ""),
                              str(payload.get("source_batch_id") or ""), str(payload.get("operator") or ""))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/customer-candidates/batches/latest")
def latest(business_month: str = "", db: Session = Depends(get_db)):
    return latest_batch(db, business_month)


@router.get("/api/customer-candidates")
def candidates(business_month: str = "", status: str = "", batch_id: str = "",
               limit: int = Query(0, ge=0), db: Session = Depends(get_db)):
    return list_candidates(db, business_month, status, batch_id, limit)


@router.post("/api/customer-candidates/{candidate_id}/resolve")
def resolve(candidate_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return resolve_candidate(db, candidate_id, str(payload.get("action") or ""),
                                 str(payload.get("reviewer") or ""), str(payload.get("comment") or ""),
                                 str(payload.get("customer_id") or ""), str(payload.get("formal_name") or ""))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/api/customer-candidates/bulk-resolve")
def bulk_resolve(payload: dict, db: Session = Depends(get_db)):
    try:
        return bulk_resolve_candidates(
            db,
            list(payload.get("candidate_ids") or []),
            str(payload.get("action") or ""),
            str(payload.get("reviewer") or ""),
            str(payload.get("comment") or ""),
            dict(payload.get("formal_names") or {}),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/customer-candidates/export.csv")
def export(business_month: str = "", status: str = "", batch_id: str = "",
           db: Session = Depends(get_db)):
    data = export_csv(list_candidates(db, business_month, status, batch_id, 0))
    return Response(data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=customer_candidates.csv"})


@router.post("/api/customer-candidates/import.csv")
async def upload_csv(request: Request, actor: str = "", db: Session = Depends(get_db)):
    try:
        return import_csv(db, await request.body(), actor)
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc

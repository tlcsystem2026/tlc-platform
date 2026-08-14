from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_bank_remitter_candidate_service import (
    export_review_csv, import_review_csv, latest_batch, list_candidates,
    resolve_candidate, run_extraction_from_csv,
)

router = APIRouter(tags=["tlc-bank-remitter-candidate"])


@router.get("/bank-remitter-candidate-center", response_class=HTMLResponse)
def page():
    path = Path(__file__).parents[2] / "web" / "static" / "bank_remitter_candidate_center.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.post("/api/bank-remitter-candidates/batches")
async def run_batch(request: Request, selected_bank_code: str = Query(..., min_length=1),
                    source_name: str = "bank.csv", operator: str = "", db: Session = Depends(get_db)):
    try:
        return run_extraction_from_csv(db, await request.body(), selected_bank_code, source_name, operator)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/bank-remitter-candidates/batches/latest")
def latest(bank_code: str = "", db: Session = Depends(get_db)):
    try:
        return latest_batch(db, bank_code=bank_code)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/bank-remitter-candidates")
def candidates(business_month: str = "", status: str = "", batch_id: str = "",
               limit: int = Query(5000, ge=0, le=10000), db: Session = Depends(get_db)):
    try:
        return list_candidates(db, business_month, status, batch_id, limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/bank-remitter-candidates/export.csv")
def export_candidates(status: str = "", batch_id: str = "", db: Session = Depends(get_db)):
    data = export_review_csv(list_candidates(db, status=status, batch_id=batch_id, limit=0))
    return Response(
        data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=bank_remitter_candidates.csv"},
    )


@router.post("/api/bank-remitter-candidates/import.csv")
async def import_candidates(request: Request, actor: str = "", db: Session = Depends(get_db)):
    try:
        return import_review_csv(db, await request.body(), actor)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/api/bank-remitter-candidates/{candidate_id}/resolve")
def resolve(candidate_id: str, payload: dict, db: Session = Depends(get_db)):
    try:
        return resolve_candidate(db, candidate_id, payload.get("action", ""), payload.get("reviewer", ""),
                                 payload.get("customer_id", ""), payload.get("comment", ""))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

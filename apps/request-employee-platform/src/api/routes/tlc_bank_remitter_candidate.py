from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_bank_remitter_candidate_service import (
    latest_batch, list_candidates, resolve_candidate, run_extraction_from_csv,
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
               limit: int = Query(5000, ge=1, le=10000), db: Session = Depends(get_db)):
    try:
        return list_candidates(db, business_month, status, batch_id, limit)
    except ValueError as exc:
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

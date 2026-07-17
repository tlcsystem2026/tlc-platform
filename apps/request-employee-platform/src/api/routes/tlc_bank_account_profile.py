from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.tlc_bank_account_profile_service import (
    import_profiles,
    list_profiles,
    save_profile,
    seed_banks,
)


router = APIRouter(tags=["tlc-bank-account-profile"])


@router.get("/api/tlc-bank-accounts")
def listing(
    bank_code: str = "",
    account_number: str = "",
    db: Session = Depends(get_db),
):
    seed_banks(db)
    return list_profiles(db, bank_code, account_number)


@router.post("/api/tlc-bank-accounts")
def saving(payload: dict, db: Session = Depends(get_db)):
    try:
        return save_profile(db, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/tlc-bank-accounts/import")
def importing(payload: dict, db: Session = Depends(get_db)):
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="rows must be an array")
    try:
        return import_profiles(db, rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/tlc-bank-accounts/template.csv")
def template_csv():
    headers = [
        "id",
        "bank_code",
        "branch_code",
        "branch_name",
        "account_type",
        "account_number",
        "account_holder",
        "adapter_code",
        "file_encoding",
        "active",
        "note",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    writer.writerow(
        {
            "bank_code": "SUGAMO_SHINKIN",
            "branch_code": "",
            "branch_name": "",
            "account_type": "",
            "account_number": "",
            "account_holder": "",
            "adapter_code": "",
            "file_encoding": "cp932",
            "active": "true",
            "note": "",
        }
    )
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="tlc_bank_account_template.csv"'
        },
    )


@router.get("/api/tlc-bank-accounts/export.csv")
def export_csv(
    bank_code: str = "",
    account_number: str = "",
    db: Session = Depends(get_db),
):
    rows = list_profiles(db, bank_code, account_number)
    headers = [
        "id",
        "bank_code",
        "branch_code",
        "branch_name",
        "account_type",
        "account_number",
        "account_holder",
        "adapter_code",
        "file_encoding",
        "active",
        "note",
        "created_at",
        "updated_at",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in headers})
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="tlc_bank_accounts.csv"'
        },
    )


@router.get("/tlc-bank-account-master", response_class=HTMLResponse)
def page():
    return HTMLResponse(
        (
            Path(__file__).parents[2]
            / "web"
            / "static"
            / "tlc_bank_account_master.html"
        ).read_text(encoding="utf-8")
    )

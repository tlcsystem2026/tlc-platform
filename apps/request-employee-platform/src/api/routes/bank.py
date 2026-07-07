from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.core.settings import get_settings
from src.services.export_service import export_xlsx, export_pdf

router = APIRouter(prefix="/api/bank", tags=["bank"])


class BankReconciliationSettingIn(BaseModel):
    legal_entity_id: str = Field(default="TEST-JP-01", min_length=1)
    bank_account_id: str = Field(default="JPBANK-001", min_length=1)
    bank_name: str = "Japan Post Bank"
    last_reconciled_date: str
    current_end_date: Optional[str] = None
    updated_by: str = "system"
    note: str = ""


def _data_dir() -> Path:
    s = get_settings()
    base = getattr(s, "document_root", None) or getattr(s, "documents_root", None) or ""
    if not base:
        base = Path.cwd() / ".tlc-data"
    p = Path(base) / "bank"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _settings_file() -> Path:
    return _data_dir() / "reconciliation_settings.json"


def _load_settings() -> list[dict]:
    path = _settings_file()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _save_settings(rows: list[dict]) -> None:
    path = _settings_file()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _next_start(last_reconciled_date: str) -> str:
    try:
        return (date.fromisoformat(last_reconciled_date) + timedelta(days=1)).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="last_reconciled_date must be YYYY-MM-DD") from exc


def _setting_key(row: dict) -> tuple[str, str]:
    return row["legal_entity_id"], row["bank_account_id"]


def _filter_settings(
    keyword: str = "",
    legal_entity_id: str = "",
    bank_account_id: str = "",
    bank_name: str = "",
):
    rows = _load_settings()
    if keyword:
        k = keyword.lower()
        rows = [x for x in rows if k in " ".join(str(v).lower() for v in x.values())]
    if legal_entity_id:
        rows = [x for x in rows if x.get("legal_entity_id") == legal_entity_id]
    if bank_account_id:
        rows = [x for x in rows if x.get("bank_account_id") == bank_account_id]
    if bank_name:
        rows = [x for x in rows if bank_name.lower() in x.get("bank_name", "").lower()]
    return sorted(rows, key=lambda x: (x.get("legal_entity_id", ""), x.get("bank_account_id", "")))


@router.get("/reconciliation/settings")
def list_reconciliation_settings(
    keyword: str = "",
    legal_entity_id: str = "",
    bank_account_id: str = "",
    bank_name: str = "",
):
    return _filter_settings(keyword, legal_entity_id, bank_account_id, bank_name)


@router.post("/reconciliation/settings")
def upsert_reconciliation_setting(req: BankReconciliationSettingIn):
    current_start_date = _next_start(req.last_reconciled_date)
    if req.current_end_date:
        try:
            date.fromisoformat(req.current_end_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="current_end_date must be YYYY-MM-DD") from exc

    now = datetime.now().isoformat(timespec="seconds")
    obj = {
        "legal_entity_id": req.legal_entity_id,
        "bank_account_id": req.bank_account_id,
        "bank_name": req.bank_name,
        "last_reconciled_date": req.last_reconciled_date,
        "current_start_date": current_start_date,
        "current_end_date": req.current_end_date or date.today().isoformat(),
        "status": "ready",
        "updated_by": req.updated_by,
        "updated_at": now,
        "note": req.note,
    }

    rows = _load_settings()
    key = _setting_key(obj)
    replaced = False
    for idx, row in enumerate(rows):
        if _setting_key(row) == key:
            rows[idx] = obj
            replaced = True
            break
    if not replaced:
        rows.append(obj)
    _save_settings(rows)
    return obj


@router.get("/reconciliation/settings/export/excel")
def export_reconciliation_settings_excel(
    keyword: str = "",
    legal_entity_id: str = "",
    bank_account_id: str = "",
    bank_name: str = "",
):
    rows = _filter_settings(keyword, legal_entity_id, bank_account_id, bank_name)
    return export_xlsx(rows, "bank_reconciliation_settings")


@router.get("/reconciliation/settings/export/pdf")
def export_reconciliation_settings_pdf(
    keyword: str = "",
    legal_entity_id: str = "",
    bank_account_id: str = "",
    bank_name: str = "",
):
    rows = _filter_settings(keyword, legal_entity_id, bank_account_id, bank_name)
    return export_pdf(rows, "bank_reconciliation_settings", "Bank Reconciliation Settings")


@router.get("/reconciliation/period")
def get_reconciliation_period(legal_entity_id: str, bank_account_id: str):
    rows = _filter_settings(legal_entity_id=legal_entity_id, bank_account_id=bank_account_id)
    if not rows:
        raise HTTPException(status_code=404, detail="reconciliation setting not found")
    row = rows[0]
    return {
        "legal_entity_id": row["legal_entity_id"],
        "bank_account_id": row["bank_account_id"],
        "last_reconciled_date": row["last_reconciled_date"],
        "current_start_date": row["current_start_date"],
        "current_end_date": row["current_end_date"],
    }


@router.get("/transactions")
def list_transactions():
    return []


@router.get("/reconciliation/list")
def list_reconciliation():
    return []

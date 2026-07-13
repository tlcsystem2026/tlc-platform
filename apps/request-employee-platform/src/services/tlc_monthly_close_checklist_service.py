
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_monthly_close_control_service import monthly_close_overview

CHECKLIST_TABLE = "tlc_monthly_close_checklist"
SIGNOFF_TABLE = "tlc_monthly_close_signoff"
DEFAULT_ITEMS = [
    ("IMPORT_COMPLETE", "导入任务完成"),
    ("COMPARE_ERRORS_CLEARED", "比较错误已处理"),
    ("IMPORT_ERRORS_CLEARED", "导入错误已处理"),
    ("REVIEW_COMPLETE", "审核完成"),
    ("SALES_LEDGER_COMPLETE", "销售台账完成"),
    ("BANK_IMPORT_COMPLETE", "银行流水完成"),
    ("RECONCILIATION_COMPLETE", "客户对账完成"),
    ("BATCH_FINISHED", "全部 Batch 已完成"),
]
ALLOWED_ITEM_STATUSES = {"PENDING", "DONE", "WAIVED"}
ALLOWED_SIGNOFF_STATUSES = {"DRAFT", "APPROVED", "REJECTED", "REOPENED"}

def ensure_tables(db: Session) -> None:
    db.execute(text(f'''
        CREATE TABLE IF NOT EXISTS {CHECKLIST_TABLE}(
          id VARCHAR(64) PRIMARY KEY,
          business_month VARCHAR(32) NOT NULL,
          item_code VARCHAR(128) NOT NULL,
          item_name VARCHAR(500) NOT NULL,
          status VARCHAR(64) NOT NULL DEFAULT 'PENDING',
          note TEXT NOT NULL DEFAULT '',
          updated_by VARCHAR(255) NOT NULL DEFAULT '',
          updated_at VARCHAR(64) NOT NULL,
          UNIQUE(business_month,item_code)
        )
    '''))
    db.execute(text(f'''
        CREATE TABLE IF NOT EXISTS {SIGNOFF_TABLE}(
          id VARCHAR(64) PRIMARY KEY,
          business_month VARCHAR(32) NOT NULL UNIQUE,
          status VARCHAR(64) NOT NULL DEFAULT 'DRAFT',
          signed_by VARCHAR(255) NOT NULL DEFAULT '',
          signed_at VARCHAR(64) NOT NULL DEFAULT '',
          note TEXT NOT NULL DEFAULT '',
          updated_by VARCHAR(255) NOT NULL DEFAULT '',
          updated_at VARCHAR(64) NOT NULL
        )
    '''))
    db.commit()

def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping)

def list_checklist(db: Session, business_month: str) -> list[dict[str, Any]]:
    ensure_tables(db)
    rows = db.execute(text(f'''
        SELECT * FROM {CHECKLIST_TABLE}
        WHERE business_month=:business_month
        ORDER BY item_code
    '''), {"business_month": business_month}).all()
    return [_row(row) for row in rows]

def get_signoff(db: Session, business_month: str) -> dict[str, Any]:
    ensure_tables(db)
    row = db.execute(text(f'''
        SELECT * FROM {SIGNOFF_TABLE}
        WHERE business_month=:business_month
    '''), {"business_month": business_month}).first()
    if not row:
        raise LookupError("Monthly close signoff not found")
    return _row(row)

def initialize_checklist(db: Session, *, business_month: str, operator: str) -> dict[str, Any]:
    ensure_tables(db)
    business_month = str(business_month or "").strip()
    operator = str(operator or "").strip()
    if not business_month:
        raise ValueError("business_month is required")
    if not operator:
        raise ValueError("operator is required")

    now = datetime.now(timezone.utc).isoformat()
    created = 0
    for code, name in DEFAULT_ITEMS:
        exists = db.execute(text(f'''
            SELECT id FROM {CHECKLIST_TABLE}
            WHERE business_month=:business_month AND item_code=:item_code
        '''), {"business_month": business_month, "item_code": code}).first()
        if exists:
            continue
        db.execute(text(f'''
            INSERT INTO {CHECKLIST_TABLE}(
              id,business_month,item_code,item_name,status,note,updated_by,updated_at
            ) VALUES(:id,:business_month,:item_code,:item_name,'PENDING','',:updated_by,:updated_at)
        '''), {
            "id": uuid4().hex,
            "business_month": business_month,
            "item_code": code,
            "item_name": name,
            "updated_by": operator,
            "updated_at": now,
        })
        created += 1

    signoff = db.execute(text(f'''
        SELECT id FROM {SIGNOFF_TABLE}
        WHERE business_month=:business_month
    '''), {"business_month": business_month}).first()
    if not signoff:
        db.execute(text(f'''
            INSERT INTO {SIGNOFF_TABLE}(
              id,business_month,status,signed_by,signed_at,note,updated_by,updated_at
            ) VALUES(:id,:business_month,'DRAFT','','','',:updated_by,:updated_at)
        '''), {
            "id": uuid4().hex,
            "business_month": business_month,
            "updated_by": operator,
            "updated_at": now,
        })
    db.commit()
    return {
        "business_month": business_month,
        "created_item_count": created,
        "checklist": list_checklist(db, business_month),
        "signoff": get_signoff(db, business_month),
    }

def update_checklist_item(
    db: Session, *, item_id: str, status: str, operator: str, note: str = ""
) -> dict[str, Any]:
    ensure_tables(db)
    current = db.execute(text(f"SELECT * FROM {CHECKLIST_TABLE} WHERE id=:id"), {"id": item_id}).first()
    if not current:
        raise LookupError("Checklist item not found")
    status = str(status or "").strip().upper()
    operator = str(operator or "").strip()
    if status not in ALLOWED_ITEM_STATUSES:
        raise ValueError("Unsupported checklist status")
    if not operator:
        raise ValueError("operator is required")
    db.execute(text(f'''
        UPDATE {CHECKLIST_TABLE}
        SET status=:status,note=:note,updated_by=:updated_by,updated_at=:updated_at
        WHERE id=:id
    '''), {
        "id": item_id,
        "status": status,
        "note": str(note or ""),
        "updated_by": operator,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    db.commit()
    row = db.execute(text(f"SELECT * FROM {CHECKLIST_TABLE} WHERE id=:id"), {"id": item_id}).first()
    return _row(row)

def signoff(
    db: Session, *, business_month: str, status: str, operator: str, note: str = ""
) -> dict[str, Any]:
    ensure_tables(db)
    current = get_signoff(db, business_month)
    status = str(status or "").strip().upper()
    operator = str(operator or "").strip()
    if status not in ALLOWED_SIGNOFF_STATUSES:
        raise ValueError("Unsupported signoff status")
    if not operator:
        raise ValueError("operator is required")

    if status == "APPROVED":
        overview = monthly_close_overview(db, business_month)
        if not overview["close_ready"]:
            raise ValueError("Monthly close is not ready")
        items = list_checklist(db, business_month)
        if not items:
            raise ValueError("Checklist is not initialized")
        if any(item["status"] not in {"DONE", "WAIVED"} for item in items):
            raise ValueError("All checklist items must be DONE or WAIVED")

    now = datetime.now(timezone.utc).isoformat()
    signed_by = operator if status in {"APPROVED", "REJECTED"} else ""
    signed_at = now if signed_by else ""
    db.execute(text(f'''
        UPDATE {SIGNOFF_TABLE}
        SET status=:status,signed_by=:signed_by,signed_at=:signed_at,
            note=:note,updated_by=:updated_by,updated_at=:updated_at
        WHERE business_month=:business_month
    '''), {
        "business_month": business_month,
        "status": status,
        "signed_by": signed_by,
        "signed_at": signed_at,
        "note": str(note or current["note"] or ""),
        "updated_by": operator,
        "updated_at": now,
    })
    db.commit()
    return get_signoff(db, business_month)

def control_view(db: Session, business_month: str) -> dict[str, Any]:
    ensure_tables(db)
    overview = monthly_close_overview(db, business_month)
    checklist = list_checklist(db, business_month)
    signoff_row = db.execute(text(f'''
        SELECT * FROM {SIGNOFF_TABLE}
        WHERE business_month=:business_month
    '''), {"business_month": business_month}).first()
    return {
        "overview": overview,
        "checklist": checklist,
        "signoff": _row(signoff_row) if signoff_row else None,
        "checklist_initialized": bool(checklist),
        "checklist_complete": bool(checklist) and all(
            item["status"] in {"DONE", "WAIVED"} for item in checklist
        ),
    }

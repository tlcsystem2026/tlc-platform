from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.request_pending_review_service import (
    TABLE_NAME,
    ensure_pending_review_table,
    get_pending_review,
)

ALLOWED_ACTIONS={
 "APPROVE":"APPROVED","REJECT":"REJECTED","CANCEL":"CANCELLED","MARK_DUPLICATE":"DUPLICATE",
 "MARK_CASH_SALE_NO_INVOICE":"CASH_SALE_NO_INVOICE","REQUIRE_AMOUNT_CORRECTION":"AMOUNT_CORRECTION_REQUIRED",
 "REQUIRE_BUSINESS_CORRECTION":"BUSINESS_CORRECTION_REQUIRED","HOLD":"ON_HOLD",
}
TERMINAL_STATUSES = set(ALLOWED_ACTIONS.values())


def ensure_review_audit_table(db: Session) -> None:
    ensure_pending_review_table(db)
    columns = {row[1] for row in db.execute(text(f"PRAGMA table_info({TABLE_NAME})")).all()}
    if "reviewed_by" not in columns:
        db.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN reviewed_by VARCHAR(255) NOT NULL DEFAULT ''"))
    if "review_note" not in columns:
        db.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN review_note TEXT NOT NULL DEFAULT ''"))
    if "reviewed_at" not in columns:
        db.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN reviewed_at VARCHAR(64) NOT NULL DEFAULT ''"))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS request_pending_review_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id VARCHAR(64) NOT NULL,
            request_no VARCHAR(255) NOT NULL,
            old_status VARCHAR(64) NOT NULL,
            new_status VARCHAR(64) NOT NULL,
            action VARCHAR(64) NOT NULL,
            reviewed_by VARCHAR(255) NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            reviewed_at VARCHAR(64) NOT NULL
        )
    """))
    db.commit()


def resolve_pending_review(db:Session,record_id:str,*,action:str,reviewed_by:str,note:str="")->dict[str,Any]:
    ensure_review_audit_table(db);action=str(action or "").strip().upper();reviewed_by=str(reviewed_by or "").strip();note=str(note or "").strip()
    if action not in ALLOWED_ACTIONS: raise ValueError("Unsupported business review action")
    if not reviewed_by: raise ValueError("reviewed_by is required")
    if action in {"REJECT","CANCEL","MARK_DUPLICATE","MARK_CASH_SALE_NO_INVOICE","REQUIRE_AMOUNT_CORRECTION","REQUIRE_BUSINESS_CORRECTION","HOLD"} and not note: raise ValueError("Business review note is required")
    current=get_pending_review(db,record_id)
    if current is None: raise LookupError("Business review record not found")
    old_status=str(current.get("status","") or "")
    if old_status in TERMINAL_STATUSES: raise ValueError(f"Record is already finalized with status {old_status}")
    if old_status!="PENDING_REVIEW": raise ValueError(f"Unsupported current status: {old_status}")
    new_status=ALLOWED_ACTIONS[action];reviewed_at=datetime.now(timezone.utc).isoformat()
    try:
        db.execute(text(f"""UPDATE {TABLE_NAME} SET status=:status,reviewed_by=:reviewed_by,review_note=:review_note,reviewed_at=:reviewed_at,updated_at=:updated_at WHERE id=:id"""),{"id":record_id,"status":new_status,"reviewed_by":reviewed_by,"review_note":note,"reviewed_at":reviewed_at,"updated_at":reviewed_at})
        db.execute(text("""INSERT INTO request_pending_review_history(record_id,request_no,old_status,new_status,action,reviewed_by,note,reviewed_at) VALUES(:record_id,:request_no,:old_status,:new_status,:action,:reviewed_by,:note,:reviewed_at)"""),{"record_id":record_id,"request_no":current["request_no"],"old_status":old_status,"new_status":new_status,"action":action,"reviewed_by":reviewed_by,"note":note,"reviewed_at":reviewed_at})
        ledger=None
        if action=="APPROVE":
            from src.services.formal_sales_ledger_service import post_approved_pending_review
            ledger=post_approved_pending_review(db,record_id,commit=False)
        db.commit()
    except Exception:
        db.rollback();raise
    return {"status":"resolved","action":action,"old_status":old_status,"new_status":new_status,"record":get_pending_review(db,record_id),"sales_ledger":ledger}

def list_review_history(db: Session, record_id: str) -> list[dict[str, Any]]:
    ensure_review_audit_table(db)
    rows = db.execute(text("""
        SELECT id, record_id, request_no, old_status, new_status,
               action, reviewed_by, note, reviewed_at
        FROM request_pending_review_history
        WHERE record_id=:record_id
        ORDER BY id ASC
    """), {"record_id": record_id}).all()
    return [dict(row._mapping) for row in rows]

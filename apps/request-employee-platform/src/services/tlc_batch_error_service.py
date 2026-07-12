from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_batch_compare_service import ensure_compare_table, latest_batch_compare
from src.services.tlc_batch_service import append_timeline, get_batch, transition_batch

ERROR_TABLE = "tlc_batch_compare_error"
ALLOWED = {"OPEN", "RESOLVED", "IGNORED"}


def ensure_error_table(db: Session) -> None:
    ensure_compare_table(db)
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {ERROR_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            batch_id VARCHAR(64) NOT NULL,
            compare_result_id VARCHAR(64) NOT NULL,
            error_no INTEGER NOT NULL,
            field VARCHAR(255) NOT NULL DEFAULT '',
            excel_value TEXT NOT NULL DEFAULT '',
            pdf_value TEXT NOT NULL DEFAULT '',
            severity VARCHAR(64) NOT NULL DEFAULT 'error',
            message TEXT NOT NULL DEFAULT '',
            status VARCHAR(64) NOT NULL DEFAULT 'OPEN',
            resolution_note TEXT NOT NULL DEFAULT '',
            resolved_by VARCHAR(255) NOT NULL DEFAULT '',
            resolved_at VARCHAR(64) NOT NULL DEFAULT '',
            created_at VARCHAR(64) NOT NULL,
            updated_at VARCHAR(64) NOT NULL,
            UNIQUE(compare_result_id, error_no)
        )
    """))
    db.commit()


def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def sync_errors(db: Session, batch_id: str, operator: str) -> dict[str, Any]:
    ensure_error_table(db)
    batch = get_batch(db, batch_id)
    if not batch:
        raise LookupError("Batch not found")
    result = latest_batch_compare(db, batch_id)
    if not result:
        raise ValueError("No compare result found")
    differences = (result.get("result") or {}).get("differences") or []
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for index, item in enumerate(differences, start=1):
        if db.execute(text(f"SELECT id FROM {ERROR_TABLE} WHERE compare_result_id=:r AND error_no=:n"), {"r": result["id"], "n": index}).first():
            continue
        if not isinstance(item, dict):
            item = dict(getattr(item, "__dict__", {}))
        db.execute(text(f"""
            INSERT INTO {ERROR_TABLE} (
                id,batch_id,compare_result_id,error_no,field,excel_value,pdf_value,
                severity,message,status,resolution_note,resolved_by,resolved_at,
                created_at,updated_at
            ) VALUES (
                :id,:batch_id,:compare_result_id,:error_no,:field,:excel_value,:pdf_value,
                :severity,:message,'OPEN','','','',:created_at,:updated_at
            )
        """), {
            "id": uuid4().hex, "batch_id": batch_id, "compare_result_id": result["id"],
            "error_no": index, "field": str(item.get("field", "") or ""),
            "excel_value": str(item.get("excel_value", "") or ""),
            "pdf_value": str(item.get("pdf_value", "") or ""),
            "severity": str(item.get("severity", "error") or "error"),
            "message": str(item.get("message", "") or ""),
            "created_at": now, "updated_at": now,
        })
        inserted += 1
    append_timeline(db, batch_id=batch_id, event_type="COMPARE_ERRORS_SYNCED",
                    old_status=batch["status"], new_status=batch["status"],
                    message=f"Inserted {inserted} compare errors", operator=operator)
    db.commit()
    return {"batch_id": batch_id, "inserted": inserted, "difference_count": len(differences)}


def list_errors(db: Session, batch_id: str) -> list[dict[str, Any]]:
    ensure_error_table(db)
    if not get_batch(db, batch_id):
        raise LookupError("Batch not found")
    rows = db.execute(text(f"SELECT * FROM {ERROR_TABLE} WHERE batch_id=:b ORDER BY compare_result_id DESC,error_no"), {"b": batch_id}).all()
    return [_row(row) for row in rows]


def update_error(db: Session, batch_id: str, error_id: str, status: str, operator: str, note: str = "") -> dict[str, Any]:
    ensure_error_table(db)
    status = str(status or "").upper().strip()
    operator = str(operator or "").strip()
    if status not in ALLOWED:
        raise ValueError("Unsupported error status")
    if not operator:
        raise ValueError("operator is required")
    current = db.execute(text(f"SELECT * FROM {ERROR_TABLE} WHERE id=:id AND batch_id=:b"), {"id": error_id, "b": batch_id}).first()
    if not current:
        raise LookupError("Compare error not found")
    now = datetime.now(timezone.utc).isoformat()
    closed = status in {"RESOLVED", "IGNORED"}
    db.execute(text(f"""
        UPDATE {ERROR_TABLE}
        SET status=:status,resolution_note=:note,resolved_by=:resolved_by,
            resolved_at=:resolved_at,updated_at=:updated_at
        WHERE id=:id
    """), {"id": error_id, "status": status, "note": note,
             "resolved_by": operator if closed else "", "resolved_at": now if closed else "",
             "updated_at": now})
    db.commit()
    return _row(db.execute(text(f"SELECT * FROM {ERROR_TABLE} WHERE id=:id"), {"id": error_id}).first())


def summary(db: Session, batch_id: str) -> dict[str, Any]:
    rows = list_errors(db, batch_id)
    counts = {"OPEN": 0, "RESOLVED": 0, "IGNORED": 0}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"batch_id": batch_id, "total": len(rows), "open": counts["OPEN"],
            "resolved": counts["RESOLVED"], "ignored": counts["IGNORED"],
            "all_closed": bool(rows) and counts["OPEN"] == 0}


def reopen_import(db: Session, batch_id: str, operator: str) -> dict[str, Any]:
    batch = get_batch(db, batch_id)
    if not batch:
        raise LookupError("Batch not found")
    if batch["status"] != "ERROR":
        raise ValueError("Only ERROR Batch can return to IMPORTING")
    return transition_batch(db, batch_id, new_status="IMPORTING", operator=operator,
                            message="Returned to Request Import for correction")


def export_csv(db: Session, batch_id: str) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["error_no", "field", "excel_value", "pdf_value", "severity", "message", "status", "resolution_note", "resolved_by", "resolved_at"])
    for row in list_errors(db, batch_id):
        writer.writerow([row["error_no"], row["field"], row["excel_value"], row["pdf_value"], row["severity"], row["message"], row["status"], row["resolution_note"], row["resolved_by"], row["resolved_at"]])
    return output.getvalue().encode("utf-8-sig")

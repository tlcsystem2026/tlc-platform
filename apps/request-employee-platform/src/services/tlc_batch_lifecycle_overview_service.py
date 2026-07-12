from __future__ import annotations
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_batch_service import TIMELINE_TABLE, ensure_batch_tables, get_batch

TABLES = {
    "request_files": "tlc_batch_import_file",
    "import_logs": "tlc_batch_import_log",
    "compare_results": "tlc_batch_compare_result",
    "compare_errors": "tlc_batch_compare_error",
    "review_links": "tlc_batch_review_link",
    "sales_ledger_links": "tlc_batch_sales_ledger_link",
    "bank_links": "tlc_batch_bank_import_link",
    "reconciliation_links": "tlc_batch_reconciliation_link",
}

def _exists(db: Session, name: str) -> bool:
    return db.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=:name"
    ), {"name": name}).first() is not None

def _count(db: Session, name: str, batch_id: str) -> int:
    if not _exists(db, name):
        return 0
    return int(db.execute(
        text(f"SELECT COUNT(*) FROM {name} WHERE batch_id=:batch_id"),
        {"batch_id": batch_id},
    ).scalar() or 0)

def _latest(db: Session, name: str, batch_id: str, column: str, order: str) -> str:
    if not _exists(db, name):
        return ""
    row = db.execute(text(
        f"SELECT {column} FROM {name} WHERE batch_id=:batch_id "
        f"ORDER BY {order} DESC LIMIT 1"
    ), {"batch_id": batch_id}).first()
    return str(row[0] or "") if row else ""

def overview(db: Session, batch_id: str) -> dict[str, Any]:
    ensure_batch_tables(db)
    batch = get_batch(db, batch_id)
    if batch is None:
        raise LookupError("Batch not found")

    counts = {key: _count(db, table, batch_id) for key, table in TABLES.items()}

    active_files = 0
    if _exists(db, TABLES["request_files"]):
        active_files = int(db.execute(text(
            f"SELECT COUNT(*) FROM {TABLES['request_files']} "
            "WHERE batch_id=:batch_id AND active=1"
        ), {"batch_id": batch_id}).scalar() or 0)

    open_errors = 0
    if _exists(db, TABLES["compare_errors"]):
        open_errors = int(db.execute(text(
            f"SELECT COUNT(*) FROM {TABLES['compare_errors']} "
            "WHERE batch_id=:batch_id AND status='OPEN'"
        ), {"batch_id": batch_id}).scalar() or 0)

    latest_compare = _latest(
        db, TABLES["compare_results"], batch_id, "status", "compared_at"
    )
    latest_review = _latest(
        db, TABLES["review_links"], batch_id, "review_status", "updated_at"
    )
    latest_reconciliation = _latest(
        db, TABLES["reconciliation_links"], batch_id,
        "reconciliation_status", "linked_at"
    )

    checks = [
        {"step": "REQUEST_IMPORT", "complete": active_files >= 2, "detail": f"active files={active_files}"},
        {"step": "COMPARE", "complete": counts["compare_results"] > 0, "detail": latest_compare or "not started"},
        {"step": "ERROR_RESOLUTION", "complete": open_errors == 0, "detail": f"open errors={open_errors}"},
        {"step": "REVIEW", "complete": counts["review_links"] > 0, "detail": latest_review or "not started"},
        {"step": "SALES_LEDGER", "complete": counts["sales_ledger_links"] > 0, "detail": f"links={counts['sales_ledger_links']}"},
        {"step": "BANK", "complete": counts["bank_links"] > 0, "detail": f"links={counts['bank_links']}"},
        {"step": "RECONCILIATION", "complete": counts["reconciliation_links"] > 0, "detail": latest_reconciliation or "not started"},
        {"step": "FINISH", "complete": batch["status"] == "FINISHED", "detail": batch["status"]},
    ]
    completed = sum(1 for item in checks if item["complete"])
    return {
        "batch": batch,
        "counts": counts,
        "active_request_file_count": active_files,
        "open_error_count": open_errors,
        "latest_compare_status": latest_compare,
        "latest_review_status": latest_review,
        "latest_reconciliation_status": latest_reconciliation,
        "checks": checks,
        "completed_step_count": completed,
        "total_step_count": len(checks),
        "completion_percent": int(completed * 100 / len(checks)),
    }

def timeline(db: Session, batch_id: str, limit: int = 500) -> list[dict[str, Any]]:
    ensure_batch_tables(db)
    if get_batch(db, batch_id) is None:
        raise LookupError("Batch not found")
    rows = db.execute(text(
        f"SELECT * FROM {TIMELINE_TABLE} WHERE batch_id=:batch_id "
        "ORDER BY event_at DESC LIMIT :limit"
    ), {
        "batch_id": batch_id,
        "limit": min(max(int(limit), 1), 1000),
    }).all()
    return [dict(row._mapping) for row in rows]

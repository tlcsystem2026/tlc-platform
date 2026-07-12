from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


BATCH_TABLE = "tlc_batch"
TIMELINE_TABLE = "tlc_batch_timeline"

ALLOWED_STATUSES = {
    "NEW",
    "IMPORTING",
    "COMPARE",
    "ERROR",
    "READY_REVIEW",
    "REVIEWING",
    "LEDGER_POSTED",
    "BANK_IMPORTED",
    "RECONCILING",
    "FINISHED",
}

STATUS_TRANSITIONS = {
    "NEW": {"IMPORTING", "FINISHED"},
    "IMPORTING": {"COMPARE", "ERROR", "FINISHED"},
    "COMPARE": {"ERROR", "READY_REVIEW", "FINISHED"},
    "ERROR": {"IMPORTING", "COMPARE", "FINISHED"},
    "READY_REVIEW": {"REVIEWING", "FINISHED"},
    "REVIEWING": {"LEDGER_POSTED", "ERROR", "FINISHED"},
    "LEDGER_POSTED": {"BANK_IMPORTED", "RECONCILING", "FINISHED"},
    "BANK_IMPORTED": {"RECONCILING", "FINISHED"},
    "RECONCILING": {"FINISHED", "ERROR"},
    "FINISHED": set(),
}


def ensure_batch_tables(db: Session) -> None:
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {BATCH_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            batch_no VARCHAR(64) NOT NULL UNIQUE,
            business_month VARCHAR(7) NOT NULL,
            sequence_no INTEGER NOT NULL,
            title VARCHAR(500) NOT NULL DEFAULT '',
            status VARCHAR(64) NOT NULL DEFAULT 'NEW',
            created_by VARCHAR(255) NOT NULL,
            owner VARCHAR(255) NOT NULL DEFAULT '',
            source_folder VARCHAR(1000) NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            closed_at VARCHAR(64) NOT NULL DEFAULT '',
            created_at VARCHAR(64) NOT NULL,
            updated_at VARCHAR(64) NOT NULL,
            UNIQUE(business_month, sequence_no)
        )
    """))
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {TIMELINE_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            batch_id VARCHAR(64) NOT NULL,
            event_type VARCHAR(128) NOT NULL,
            old_status VARCHAR(64) NOT NULL DEFAULT '',
            new_status VARCHAR(64) NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            operator VARCHAR(255) NOT NULL DEFAULT '',
            event_at VARCHAR(64) NOT NULL
        )
    """))
    db.commit()


def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping if hasattr(row, "_mapping") else row)


def _normalize_business_month(value: str) -> str:
    raw = str(value or "").strip()
    if len(raw) == 6 and raw.isdigit():
        raw = f"{raw[:4]}-{raw[4:]}"
    if len(raw) != 7 or raw[4] != "-":
        raise ValueError("business_month must be YYYY-MM or YYYYMM")
    year, month = raw.split("-", 1)
    if not (year.isdigit() and month.isdigit()):
        raise ValueError("business_month must be YYYY-MM or YYYYMM")
    month_number = int(month)
    if month_number < 1 or month_number > 12:
        raise ValueError("business_month month must be between 01 and 12")
    return f"{int(year):04d}-{month_number:02d}"


def _next_sequence(db: Session, business_month: str) -> int:
    value = db.execute(text(f"""
        SELECT COALESCE(MAX(sequence_no), 0)
        FROM {BATCH_TABLE}
        WHERE business_month=:business_month
    """), {"business_month": business_month}).scalar()
    return int(value or 0) + 1


def _batch_no(business_month: str, sequence_no: int) -> str:
    return f"{business_month.replace('-', '')}-{sequence_no:03d}"


def append_timeline(
    db: Session,
    *,
    batch_id: str,
    event_type: str,
    old_status: str = "",
    new_status: str = "",
    message: str = "",
    operator: str = "",
) -> None:
    db.execute(text(f"""
        INSERT INTO {TIMELINE_TABLE} (
            id, batch_id, event_type, old_status, new_status,
            message, operator, event_at
        ) VALUES (
            :id, :batch_id, :event_type, :old_status, :new_status,
            :message, :operator, :event_at
        )
    """), {
        "id": uuid4().hex,
        "batch_id": batch_id,
        "event_type": event_type,
        "old_status": old_status,
        "new_status": new_status,
        "message": message,
        "operator": operator,
        "event_at": datetime.now(timezone.utc).isoformat(),
    })


def create_batch(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_batch_tables(db)

    business_month = _normalize_business_month(
        payload.get("business_month", "")
    )
    created_by = str(payload.get("created_by", "") or "").strip()
    if not created_by:
        raise ValueError("created_by is required")

    sequence_no = _next_sequence(db, business_month)
    batch_no = _batch_no(business_month, sequence_no)
    now = datetime.now(timezone.utc).isoformat()
    batch_id = uuid4().hex

    params = {
        "id": batch_id,
        "batch_no": batch_no,
        "business_month": business_month,
        "sequence_no": sequence_no,
        "title": str(payload.get("title", "") or "").strip(),
        "status": "NEW",
        "created_by": created_by,
        "owner": str(payload.get("owner", "") or "").strip(),
        "source_folder": str(payload.get("source_folder", "") or "").strip(),
        "note": str(payload.get("note", "") or ""),
        "closed_at": "",
        "created_at": now,
        "updated_at": now,
    }

    db.execute(text(f"""
        INSERT INTO {BATCH_TABLE} (
            id, batch_no, business_month, sequence_no, title, status,
            created_by, owner, source_folder, note, closed_at,
            created_at, updated_at
        ) VALUES (
            :id, :batch_no, :business_month, :sequence_no, :title, :status,
            :created_by, :owner, :source_folder, :note, :closed_at,
            :created_at, :updated_at
        )
    """), params)

    append_timeline(
        db,
        batch_id=batch_id,
        event_type="BATCH_CREATED",
        new_status="NEW",
        message=f"Batch {batch_no} created",
        operator=created_by,
    )
    db.commit()

    return get_batch(db, batch_id)


def list_batches(
    db: Session,
    *,
    business_month: str = "",
    status: str = "",
    query: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    ensure_batch_tables(db)

    clauses = []
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 1000)}

    if business_month:
        params["business_month"] = _normalize_business_month(business_month)
        clauses.append("business_month=:business_month")
    if status:
        normalized_status = str(status).strip().upper()
        if normalized_status not in ALLOWED_STATUSES:
            raise ValueError("Unsupported batch status")
        params["status"] = normalized_status
        clauses.append("status=:status")
    if query:
        params["query"] = f"%{query}%"
        clauses.append(
            "(batch_no LIKE :query OR title LIKE :query "
            "OR owner LIKE :query OR note LIKE :query)"
        )

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(text(f"""
        SELECT *
        FROM {BATCH_TABLE}
        {where}
        ORDER BY business_month DESC, sequence_no DESC
        LIMIT :limit
    """), params).all()

    return [_row(row) for row in rows]


def get_batch(db: Session, batch_id: str) -> dict[str, Any] | None:
    ensure_batch_tables(db)
    row = db.execute(
        text(f"SELECT * FROM {BATCH_TABLE} WHERE id=:id"),
        {"id": batch_id},
    ).first()
    return _row(row) if row else None


def update_batch(
    db: Session,
    batch_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    ensure_batch_tables(db)
    current = get_batch(db, batch_id)
    if current is None:
        raise LookupError("Batch not found")

    if current["status"] == "FINISHED":
        raise ValueError("Finished batch cannot be edited")

    now = datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""
        UPDATE {BATCH_TABLE}
        SET title=:title,
            owner=:owner,
            source_folder=:source_folder,
            note=:note,
            updated_at=:updated_at
        WHERE id=:id
    """), {
        "id": batch_id,
        "title": str(payload.get("title", current["title"]) or "").strip(),
        "owner": str(payload.get("owner", current["owner"]) or "").strip(),
        "source_folder": str(
            payload.get("source_folder", current["source_folder"]) or ""
        ).strip(),
        "note": str(payload.get("note", current["note"]) or ""),
        "updated_at": now,
    })

    append_timeline(
        db,
        batch_id=batch_id,
        event_type="BATCH_UPDATED",
        old_status=current["status"],
        new_status=current["status"],
        message="Batch basic information updated",
        operator=str(payload.get("operator", "") or "").strip(),
    )
    db.commit()
    return get_batch(db, batch_id)


def transition_batch(
    db: Session,
    batch_id: str,
    *,
    new_status: str,
    operator: str,
    message: str = "",
) -> dict[str, Any]:
    ensure_batch_tables(db)
    current = get_batch(db, batch_id)
    if current is None:
        raise LookupError("Batch not found")

    new_status = str(new_status or "").strip().upper()
    operator = str(operator or "").strip()
    if new_status not in ALLOWED_STATUSES:
        raise ValueError("Unsupported batch status")
    if not operator:
        raise ValueError("operator is required")

    old_status = current["status"]
    if new_status == old_status:
        return current

    allowed = STATUS_TRANSITIONS.get(old_status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Invalid batch status transition: {old_status} -> {new_status}"
        )

    now = datetime.now(timezone.utc).isoformat()
    closed_at = now if new_status == "FINISHED" else current["closed_at"]

    db.execute(text(f"""
        UPDATE {BATCH_TABLE}
        SET status=:status,
            closed_at=:closed_at,
            updated_at=:updated_at
        WHERE id=:id
    """), {
        "id": batch_id,
        "status": new_status,
        "closed_at": closed_at,
        "updated_at": now,
    })

    append_timeline(
        db,
        batch_id=batch_id,
        event_type="STATUS_CHANGED",
        old_status=old_status,
        new_status=new_status,
        message=message or f"{old_status} -> {new_status}",
        operator=operator,
    )
    db.commit()
    return get_batch(db, batch_id)


def list_timeline(db: Session, batch_id: str) -> list[dict[str, Any]]:
    ensure_batch_tables(db)
    if get_batch(db, batch_id) is None:
        raise LookupError("Batch not found")

    rows = db.execute(text(f"""
        SELECT *
        FROM {TIMELINE_TABLE}
        WHERE batch_id=:batch_id
        ORDER BY event_at DESC
    """), {"batch_id": batch_id}).all()
    return [_row(row) for row in rows]

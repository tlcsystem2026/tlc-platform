from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_batch_service import get_batch


TABLE_NAME = "tlc_import_job"

ALLOWED_IMPORT_TYPES = {
    "REQUEST_EXCEL",
    "REQUEST_PDF",
    "BANK_CSV",
    "BANK_EXCEL",
    "BANK_PDF",
    "PURCHASE_EXCEL",
    "PURCHASE_PDF",
    "PURCHASE_IMAGE",
}

ALLOWED_STATUSES = {
    "NEW",
    "STAGED",
    "PROCESSING",
    "SUCCESS",
    "ERROR",
    "CANCELLED",
}

STATUS_TRANSITIONS = {
    "NEW": {"STAGED", "PROCESSING", "CANCELLED"},
    "STAGED": {"PROCESSING", "CANCELLED"},
    "PROCESSING": {"SUCCESS", "ERROR", "CANCELLED"},
    "ERROR": {"PROCESSING", "CANCELLED"},
    "SUCCESS": set(),
    "CANCELLED": set(),
}


def ensure_table(db: Session) -> None:
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id VARCHAR(64) PRIMARY KEY,
            batch_id VARCHAR(64) NOT NULL,
            import_type VARCHAR(64) NOT NULL,
            source_name VARCHAR(1000) NOT NULL DEFAULT '',
            source_reference VARCHAR(2000) NOT NULL DEFAULT '',
            status VARCHAR(64) NOT NULL DEFAULT 'NEW',
            record_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            duplicate_count INTEGER NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            created_by VARCHAR(255) NOT NULL,
            created_at VARCHAR(64) NOT NULL,
            updated_by VARCHAR(255) NOT NULL DEFAULT '',
            updated_at VARCHAR(64) NOT NULL,
            UNIQUE(batch_id, import_type, source_reference)
        )
    """))
    db.commit()


def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping if hasattr(row, "_mapping") else row)


def create_job(
    db: Session,
    *,
    batch_id: str,
    import_type: str,
    source_name: str,
    source_reference: str,
    created_by: str,
    message: str = "",
) -> dict[str, Any]:
    ensure_table(db)

    batch = get_batch(db, batch_id)
    if batch is None:
        raise LookupError("Batch not found")
    if batch["status"] == "FINISHED":
        raise ValueError("Finished batch cannot accept new import jobs")

    import_type = str(import_type or "").strip().upper()
    created_by = str(created_by or "").strip()
    source_reference = str(source_reference or "").strip()
    source_name = str(source_name or "").strip()

    if import_type not in ALLOWED_IMPORT_TYPES:
        raise ValueError("Unsupported import type")
    if not created_by:
        raise ValueError("created_by is required")
    if not source_reference:
        raise ValueError("source_reference is required")

    existing = db.execute(text(f"""
        SELECT *
        FROM {TABLE_NAME}
        WHERE batch_id=:batch_id
          AND import_type=:import_type
          AND source_reference=:source_reference
    """), {
        "batch_id": batch_id,
        "import_type": import_type,
        "source_reference": source_reference,
    }).first()
    if existing:
        return {"status": "exists", "job": _row(existing)}

    now = datetime.now(timezone.utc).isoformat()
    job_id = uuid4().hex
    db.execute(text(f"""
        INSERT INTO {TABLE_NAME} (
            id, batch_id, import_type,
            source_name, source_reference,
            status, record_count, success_count,
            error_count, duplicate_count,
            message, created_by, created_at,
            updated_by, updated_at
        ) VALUES (
            :id, :batch_id, :import_type,
            :source_name, :source_reference,
            'NEW', 0, 0, 0, 0,
            :message, :created_by, :created_at,
            :created_by, :updated_at
        )
    """), {
        "id": job_id,
        "batch_id": batch_id,
        "import_type": import_type,
        "source_name": source_name,
        "source_reference": source_reference,
        "message": str(message or ""),
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    })
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),
        {"id": job_id},
    ).first()
    return {"status": "created", "job": _row(row)}


def list_jobs(
    db: Session,
    *,
    batch_id: str = "",
    import_type: str = "",
    status: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    ensure_table(db)

    clauses = []
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 1000)}

    if batch_id:
        if get_batch(db, batch_id) is None:
            raise LookupError("Batch not found")
        clauses.append("batch_id=:batch_id")
        params["batch_id"] = batch_id

    if import_type:
        normalized_type = import_type.strip().upper()
        if normalized_type not in ALLOWED_IMPORT_TYPES:
            raise ValueError("Unsupported import type")
        clauses.append("import_type=:import_type")
        params["import_type"] = normalized_type

    if status:
        normalized_status = status.strip().upper()
        if normalized_status not in ALLOWED_STATUSES:
            raise ValueError("Unsupported import status")
        clauses.append("status=:status")
        params["status"] = normalized_status

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(text(f"""
        SELECT *
        FROM {TABLE_NAME}
        {where}
        ORDER BY created_at DESC
        LIMIT :limit
    """), params).all()

    return [_row(row) for row in rows]


def update_job(
    db: Session,
    *,
    job_id: str,
    status: str,
    operator: str,
    record_count: int | None = None,
    success_count: int | None = None,
    error_count: int | None = None,
    duplicate_count: int | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    ensure_table(db)

    current = db.execute(
        text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),
        {"id": job_id},
    ).first()
    if not current:
        raise LookupError("Import job not found")

    current_row = _row(current)
    status = str(status or "").strip().upper()
    operator = str(operator or "").strip()

    if status not in ALLOWED_STATUSES:
        raise ValueError("Unsupported import status")
    if not operator:
        raise ValueError("operator is required")
    if status != current_row["status"]:
        allowed = STATUS_TRANSITIONS.get(current_row["status"], set())
        if status not in allowed:
            raise ValueError(
                f"Invalid import status transition: "
                f"{current_row['status']} -> {status}"
            )

    values = {
        "id": job_id,
        "status": status,
        "record_count": (
            current_row["record_count"]
            if record_count is None else max(int(record_count), 0)
        ),
        "success_count": (
            current_row["success_count"]
            if success_count is None else max(int(success_count), 0)
        ),
        "error_count": (
            current_row["error_count"]
            if error_count is None else max(int(error_count), 0)
        ),
        "duplicate_count": (
            current_row["duplicate_count"]
            if duplicate_count is None else max(int(duplicate_count), 0)
        ),
        "message": current_row["message"] if message is None else str(message),
        "updated_by": operator,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    db.execute(text(f"""
        UPDATE {TABLE_NAME}
        SET status=:status,
            record_count=:record_count,
            success_count=:success_count,
            error_count=:error_count,
            duplicate_count=:duplicate_count,
            message=:message,
            updated_by=:updated_by,
            updated_at=:updated_at
        WHERE id=:id
    """), values)
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),
        {"id": job_id},
    ).first()
    return _row(row)


def summary(db: Session, batch_id: str = "") -> dict[str, Any]:
    jobs = list_jobs(db, batch_id=batch_id, limit=1000)
    return {
        "batch_id": batch_id,
        "job_count": len(jobs),
        "new_count": sum(1 for job in jobs if job["status"] == "NEW"),
        "processing_count": sum(
            1 for job in jobs if job["status"] in {"STAGED", "PROCESSING"}
        ),
        "success_count": sum(1 for job in jobs if job["status"] == "SUCCESS"),
        "error_count": sum(1 for job in jobs if job["status"] == "ERROR"),
        "cancelled_count": sum(
            1 for job in jobs if job["status"] == "CANCELLED"
        ),
        "record_count": sum(int(job["record_count"]) for job in jobs),
        "imported_record_count": sum(int(job["success_count"]) for job in jobs),
        "error_record_count": sum(int(job["error_count"]) for job in jobs),
        "duplicate_record_count": sum(
            int(job["duplicate_count"]) for job in jobs
        ),
    }

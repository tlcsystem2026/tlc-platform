
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_import_center_service import (
    TABLE_NAME as IMPORT_JOB_TABLE,
    ensure_table as ensure_import_job_table,
    update_job,
)

ERROR_TABLE = "tlc_import_job_error"
RETRY_TABLE = "tlc_import_job_retry"

ALLOWED_ERROR_STATUSES = {"OPEN", "RESOLVED", "IGNORED"}
ALLOWED_RETRY_STATUSES = {"REQUESTED", "PROCESSING", "SUCCESS", "ERROR", "CANCELLED"}


def ensure_tables(db: Session) -> None:
    ensure_import_job_table(db)
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {ERROR_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            import_job_id VARCHAR(64) NOT NULL,
            batch_id VARCHAR(64) NOT NULL,
            error_code VARCHAR(128) NOT NULL DEFAULT '',
            record_reference VARCHAR(1000) NOT NULL DEFAULT '',
            field_name VARCHAR(255) NOT NULL DEFAULT '',
            source_value TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            status VARCHAR(64) NOT NULL DEFAULT 'OPEN',
            resolution_note TEXT NOT NULL DEFAULT '',
            resolved_by VARCHAR(255) NOT NULL DEFAULT '',
            resolved_at VARCHAR(64) NOT NULL DEFAULT '',
            created_at VARCHAR(64) NOT NULL,
            updated_at VARCHAR(64) NOT NULL
        )
    """))
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {RETRY_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            import_job_id VARCHAR(64) NOT NULL,
            batch_id VARCHAR(64) NOT NULL,
            retry_no INTEGER NOT NULL,
            status VARCHAR(64) NOT NULL DEFAULT 'REQUESTED',
            requested_by VARCHAR(255) NOT NULL,
            requested_at VARCHAR(64) NOT NULL,
            started_at VARCHAR(64) NOT NULL DEFAULT '',
            completed_at VARCHAR(64) NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            UNIQUE(import_job_id, retry_no)
        )
    """))
    db.commit()


def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping if hasattr(row, "_mapping") else row)


def _get_job(db: Session, job_id: str) -> dict[str, Any]:
    ensure_tables(db)
    row = db.execute(
        text(f"SELECT * FROM {IMPORT_JOB_TABLE} WHERE id=:id"),
        {"id": job_id},
    ).first()
    if not row:
        raise LookupError("Import job not found")
    return _row(row)


def create_error(
    db: Session,
    *,
    import_job_id: str,
    error_code: str = "",
    record_reference: str = "",
    field_name: str = "",
    source_value: str = "",
    message: str = "",
) -> dict[str, Any]:
    job = _get_job(db, import_job_id)
    now = datetime.now(timezone.utc).isoformat()
    error_id = uuid4().hex

    db.execute(text(f"""
        INSERT INTO {ERROR_TABLE} (
            id, import_job_id, batch_id,
            error_code, record_reference, field_name,
            source_value, message, status,
            resolution_note, resolved_by, resolved_at,
            created_at, updated_at
        ) VALUES (
            :id, :import_job_id, :batch_id,
            :error_code, :record_reference, :field_name,
            :source_value, :message, 'OPEN',
            '', '', '', :created_at, :updated_at
        )
    """), {
        "id": error_id,
        "import_job_id": import_job_id,
        "batch_id": job["batch_id"],
        "error_code": str(error_code or ""),
        "record_reference": str(record_reference or ""),
        "field_name": str(field_name or ""),
        "source_value": str(source_value or ""),
        "message": str(message or ""),
        "created_at": now,
        "updated_at": now,
    })
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {ERROR_TABLE} WHERE id=:id"),
        {"id": error_id},
    ).first()
    return _row(row)


def list_errors(
    db: Session,
    *,
    import_job_id: str = "",
    batch_id: str = "",
    status: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    ensure_tables(db)
    clauses = []
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 1000)}

    if import_job_id:
        clauses.append("import_job_id=:import_job_id")
        params["import_job_id"] = import_job_id

    if batch_id:
        clauses.append("batch_id=:batch_id")
        params["batch_id"] = batch_id

    if status:
        normalized = status.strip().upper()
        if normalized not in ALLOWED_ERROR_STATUSES:
            raise ValueError("Unsupported error status")
        clauses.append("status=:status")
        params["status"] = normalized

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(text(f"""
        SELECT *
        FROM {ERROR_TABLE}
        {where}
        ORDER BY created_at DESC
        LIMIT :limit
    """), params).all()
    return [_row(row) for row in rows]


def update_error(
    db: Session,
    *,
    error_id: str,
    status: str,
    operator: str,
    resolution_note: str = "",
) -> dict[str, Any]:
    ensure_tables(db)
    current = db.execute(
        text(f"SELECT * FROM {ERROR_TABLE} WHERE id=:id"),
        {"id": error_id},
    ).first()
    if not current:
        raise LookupError("Import error not found")

    normalized = str(status or "").strip().upper()
    operator = str(operator or "").strip()
    if normalized not in ALLOWED_ERROR_STATUSES:
        raise ValueError("Unsupported error status")
    if not operator:
        raise ValueError("operator is required")

    now = datetime.now(timezone.utc).isoformat()
    resolved_at = now if normalized in {"RESOLVED", "IGNORED"} else ""
    resolved_by = operator if resolved_at else ""

    db.execute(text(f"""
        UPDATE {ERROR_TABLE}
        SET status=:status,
            resolution_note=:resolution_note,
            resolved_by=:resolved_by,
            resolved_at=:resolved_at,
            updated_at=:updated_at
        WHERE id=:id
    """), {
        "id": error_id,
        "status": normalized,
        "resolution_note": str(resolution_note or ""),
        "resolved_by": resolved_by,
        "resolved_at": resolved_at,
        "updated_at": now,
    })
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {ERROR_TABLE} WHERE id=:id"),
        {"id": error_id},
    ).first()
    return _row(row)


def request_retry(
    db: Session,
    *,
    import_job_id: str,
    requested_by: str,
    message: str = "",
) -> dict[str, Any]:
    job = _get_job(db, import_job_id)
    requested_by = str(requested_by or "").strip()
    if not requested_by:
        raise ValueError("requested_by is required")
    if job["status"] not in {"ERROR", "STAGED"}:
        raise ValueError("Only ERROR or STAGED import jobs can be retried")

    next_no = int(db.execute(text(f"""
        SELECT COALESCE(MAX(retry_no), 0) + 1
        FROM {RETRY_TABLE}
        WHERE import_job_id=:import_job_id
    """), {"import_job_id": import_job_id}).scalar() or 1)

    now = datetime.now(timezone.utc).isoformat()
    retry_id = uuid4().hex
    db.execute(text(f"""
        INSERT INTO {RETRY_TABLE} (
            id, import_job_id, batch_id, retry_no,
            status, requested_by, requested_at,
            started_at, completed_at, message
        ) VALUES (
            :id, :import_job_id, :batch_id, :retry_no,
            'REQUESTED', :requested_by, :requested_at,
            '', '', :message
        )
    """), {
        "id": retry_id,
        "import_job_id": import_job_id,
        "batch_id": job["batch_id"],
        "retry_no": next_no,
        "requested_by": requested_by,
        "requested_at": now,
        "message": str(message or ""),
    })
    db.commit()

    # Normalize common job lifecycle for retry start.
    update_job(
        db,
        job_id=import_job_id,
        status="PROCESSING",
        operator=requested_by,
        message=message or f"Retry #{next_no} requested",
    )

    db.execute(text(f"""
        UPDATE {RETRY_TABLE}
        SET status='PROCESSING',
            started_at=:started_at
        WHERE id=:id
    """), {"id": retry_id, "started_at": now})
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {RETRY_TABLE} WHERE id=:id"),
        {"id": retry_id},
    ).first()
    return _row(row)


def complete_retry(
    db: Session,
    *,
    retry_id: str,
    status: str,
    operator: str,
    record_count: int = 0,
    success_count: int = 0,
    error_count: int = 0,
    duplicate_count: int = 0,
    message: str = "",
) -> dict[str, Any]:
    ensure_tables(db)
    current = db.execute(
        text(f"SELECT * FROM {RETRY_TABLE} WHERE id=:id"),
        {"id": retry_id},
    ).first()
    if not current:
        raise LookupError("Import retry not found")

    retry = _row(current)
    normalized = str(status or "").strip().upper()
    operator = str(operator or "").strip()
    if normalized not in {"SUCCESS", "ERROR", "CANCELLED"}:
        raise ValueError("Retry completion status must be SUCCESS, ERROR or CANCELLED")
    if not operator:
        raise ValueError("operator is required")

    now = datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""
        UPDATE {RETRY_TABLE}
        SET status=:status,
            completed_at=:completed_at,
            message=:message
        WHERE id=:id
    """), {
        "id": retry_id,
        "status": normalized,
        "completed_at": now,
        "message": str(message or retry["message"] or ""),
    })
    db.commit()

    job_status = "SUCCESS" if normalized == "SUCCESS" else (
        "ERROR" if normalized == "ERROR" else "CANCELLED"
    )
    update_job(
        db,
        job_id=retry["import_job_id"],
        status=job_status,
        operator=operator,
        record_count=record_count,
        success_count=success_count,
        error_count=error_count,
        duplicate_count=duplicate_count,
        message=message or f"Retry #{retry['retry_no']} completed: {normalized}",
    )

    row = db.execute(
        text(f"SELECT * FROM {RETRY_TABLE} WHERE id=:id"),
        {"id": retry_id},
    ).first()
    return _row(row)


def list_retries(
    db: Session,
    *,
    import_job_id: str = "",
    batch_id: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    ensure_tables(db)
    clauses = []
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 1000)}

    if import_job_id:
        clauses.append("import_job_id=:import_job_id")
        params["import_job_id"] = import_job_id
    if batch_id:
        clauses.append("batch_id=:batch_id")
        params["batch_id"] = batch_id

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(text(f"""
        SELECT *
        FROM {RETRY_TABLE}
        {where}
        ORDER BY requested_at DESC
        LIMIT :limit
    """), params).all()
    return [_row(row) for row in rows]


def summary(db: Session, batch_id: str = "") -> dict[str, Any]:
    errors = list_errors(db, batch_id=batch_id, limit=1000)
    retries = list_retries(db, batch_id=batch_id, limit=1000)
    return {
        "batch_id": batch_id,
        "error_count": len(errors),
        "open_error_count": sum(1 for item in errors if item["status"] == "OPEN"),
        "resolved_error_count": sum(
            1 for item in errors if item["status"] == "RESOLVED"
        ),
        "ignored_error_count": sum(
            1 for item in errors if item["status"] == "IGNORED"
        ),
        "retry_count": len(retries),
        "retry_success_count": sum(
            1 for item in retries if item["status"] == "SUCCESS"
        ),
        "retry_error_count": sum(
            1 for item in retries if item["status"] == "ERROR"
        ),
        "retry_processing_count": sum(
            1 for item in retries if item["status"] in {"REQUESTED", "PROCESSING"}
        ),
    }

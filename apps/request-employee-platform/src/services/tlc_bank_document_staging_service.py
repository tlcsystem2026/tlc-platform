
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_import_center_service import create_job, ensure_table as ensure_import_job_table, update_job

STAGE_TABLE = "tlc_bank_document_stage"
ALLOWED_DOCUMENT_TYPES = {"BANK_EXCEL", "BANK_PDF"}
ALLOWED_STAGE_STATUSES = {"STAGED", "VALIDATED", "READY", "ERROR", "CANCELLED"}
STAGE_TRANSITIONS = {
    "STAGED": {"VALIDATED", "ERROR", "CANCELLED"},
    "VALIDATED": {"READY", "ERROR", "CANCELLED"},
    "ERROR": {"VALIDATED", "CANCELLED"},
    "READY": set(),
    "CANCELLED": set(),
}

def ensure_table(db: Session) -> None:
    ensure_import_job_table(db)
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {STAGE_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            batch_id VARCHAR(64) NOT NULL,
            import_job_id VARCHAR(64) NOT NULL,
            document_type VARCHAR(64) NOT NULL,
            original_name VARCHAR(1000) NOT NULL,
            source_reference VARCHAR(2000) NOT NULL,
            content_type VARCHAR(255) NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL DEFAULT 0,
            sha256 VARCHAR(64) NOT NULL,
            bank_name VARCHAR(255) NOT NULL DEFAULT '',
            account_reference VARCHAR(255) NOT NULL DEFAULT '',
            stage_status VARCHAR(64) NOT NULL DEFAULT 'STAGED',
            parser_contract VARCHAR(255) NOT NULL DEFAULT '',
            validation_message TEXT NOT NULL DEFAULT '',
            staged_by VARCHAR(255) NOT NULL,
            staged_at VARCHAR(64) NOT NULL,
            updated_by VARCHAR(255) NOT NULL DEFAULT '',
            updated_at VARCHAR(64) NOT NULL,
            UNIQUE(batch_id, document_type, sha256),
            UNIQUE(import_job_id)
        )
    """))
    db.commit()

def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping)

def _validate_extension(document_type: str, original_name: str) -> None:
    suffix = Path(original_name).suffix.lower()
    if document_type == "BANK_EXCEL" and suffix not in {".xlsx", ".xlsm", ".xls"}:
        raise ValueError("BANK_EXCEL requires .xlsx, .xlsm or .xls")
    if document_type == "BANK_PDF" and suffix != ".pdf":
        raise ValueError("BANK_PDF requires .pdf")

def stage_document(
    db: Session, *, batch_id: str, document_type: str, original_name: str,
    source_reference: str, staged_by: str, content: bytes,
    content_type: str = "", bank_name: str = "", account_reference: str = "",
) -> dict[str, Any]:
    ensure_table(db)
    document_type = str(document_type or "").strip().upper()
    original_name = Path(str(original_name or "").strip()).name
    source_reference = str(source_reference or "").strip()
    staged_by = str(staged_by or "").strip()
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError("Unsupported bank document type")
    if not original_name or not source_reference or not staged_by or not content:
        raise ValueError("original_name, source_reference, staged_by and content are required")
    _validate_extension(document_type, original_name)

    digest = hashlib.sha256(content).hexdigest()
    existing = db.execute(text(f"""
        SELECT * FROM {STAGE_TABLE}
        WHERE batch_id=:batch_id AND document_type=:document_type AND sha256=:sha256
    """), {"batch_id": batch_id, "document_type": document_type, "sha256": digest}).first()
    if existing:
        return {"status": "exists", "stage": _row(existing)}

    job_result = create_job(
        db, batch_id=batch_id, import_type=document_type,
        source_name=original_name, source_reference=source_reference,
        created_by=staged_by, message=f"{document_type} staged for future parser",
    )
    job = job_result["job"]
    if job_result["status"] == "created":
        job = update_job(
            db, job_id=job["id"], status="STAGED", operator=staged_by,
            message="Bank document staged; parser not executed yet",
        )

    stage_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""
        INSERT INTO {STAGE_TABLE} (
            id,batch_id,import_job_id,document_type,original_name,source_reference,
            content_type,file_size,sha256,bank_name,account_reference,stage_status,
            parser_contract,validation_message,staged_by,staged_at,updated_by,updated_at
        ) VALUES (
            :id,:batch_id,:import_job_id,:document_type,:original_name,:source_reference,
            :content_type,:file_size,:sha256,:bank_name,:account_reference,'STAGED',
            '','',:staged_by,:staged_at,:staged_by,:updated_at
        )
    """), {
        "id": stage_id, "batch_id": batch_id, "import_job_id": job["id"],
        "document_type": document_type, "original_name": original_name,
        "source_reference": source_reference, "content_type": str(content_type or ""),
        "file_size": len(content), "sha256": digest, "bank_name": str(bank_name or ""),
        "account_reference": str(account_reference or ""), "staged_by": staged_by,
        "staged_at": now, "updated_at": now,
    })
    db.commit()
    row = db.execute(text(f"SELECT * FROM {STAGE_TABLE} WHERE id=:id"), {"id": stage_id}).first()
    return {"status": "staged", "stage": _row(row), "job": job}

def update_stage(
    db: Session, *, stage_id: str, stage_status: str, operator: str,
    parser_contract: str = "", validation_message: str = "",
) -> dict[str, Any]:
    ensure_table(db)
    current = db.execute(text(f"SELECT * FROM {STAGE_TABLE} WHERE id=:id"), {"id": stage_id}).first()
    if not current:
        raise LookupError("Bank document stage not found")
    record = _row(current)
    stage_status = str(stage_status or "").strip().upper()
    operator = str(operator or "").strip()
    if stage_status not in ALLOWED_STAGE_STATUSES:
        raise ValueError("Unsupported stage status")
    if not operator:
        raise ValueError("operator is required")
    if stage_status != record["stage_status"] and stage_status not in STAGE_TRANSITIONS.get(record["stage_status"], set()):
        raise ValueError(f"Invalid stage status transition: {record['stage_status']} -> {stage_status}")

    db.execute(text(f"""
        UPDATE {STAGE_TABLE}
        SET stage_status=:stage_status,parser_contract=:parser_contract,
            validation_message=:validation_message,updated_by=:operator,updated_at=:updated_at
        WHERE id=:id
    """), {
        "id": stage_id, "stage_status": stage_status,
        "parser_contract": str(parser_contract or record["parser_contract"] or ""),
        "validation_message": str(validation_message or record["validation_message"] or ""),
        "operator": operator, "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    if stage_status == "ERROR":
        update_job(db, job_id=record["import_job_id"], status="PROCESSING", operator=operator)
        update_job(
            db, job_id=record["import_job_id"], status="ERROR", operator=operator,
            error_count=1, message=validation_message or "Bank document validation failed",
        )
    elif stage_status == "READY":
        update_job(db, job_id=record["import_job_id"], status="PROCESSING", operator=operator)
        update_job(
            db, job_id=record["import_job_id"], status="SUCCESS", operator=operator,
            success_count=1, message="Bank document contract is ready",
        )
    db.commit()
    row = db.execute(text(f"SELECT * FROM {STAGE_TABLE} WHERE id=:id"), {"id": stage_id}).first()
    return _row(row)

def list_stages(db: Session, batch_id: str = "", limit: int = 500) -> list[dict[str, Any]]:
    ensure_table(db)
    params = {"limit": min(max(int(limit), 1), 1000)}
    where = ""
    if batch_id:
        where = "WHERE batch_id=:batch_id"
        params["batch_id"] = batch_id
    rows = db.execute(text(f"""
        SELECT * FROM {STAGE_TABLE} {where}
        ORDER BY staged_at DESC LIMIT :limit
    """), params).all()
    return [_row(row) for row in rows]

def summary(db: Session, batch_id: str = "") -> dict[str, Any]:
    rows = list_stages(db, batch_id=batch_id, limit=1000)
    return {
        "batch_id": batch_id,
        "stage_count": len(rows),
        "excel_count": sum(1 for row in rows if row["document_type"] == "BANK_EXCEL"),
        "pdf_count": sum(1 for row in rows if row["document_type"] == "BANK_PDF"),
        "staged_count": sum(1 for row in rows if row["stage_status"] == "STAGED"),
        "ready_count": sum(1 for row in rows if row["stage_status"] == "READY"),
        "error_count": sum(1 for row in rows if row["stage_status"] == "ERROR"),
    }


from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_import_center_service import (
    create_job,
    ensure_table as ensure_import_job_table,
    update_job,
)

STAGE_TABLE = "tlc_purchase_request_stage"
ALLOWED_TYPES = {"PURCHASE_EXCEL", "PURCHASE_PDF", "PURCHASE_IMAGE"}
ALLOWED_STATUSES = {"STAGED", "VALIDATED", "READY", "ERROR", "CANCELLED"}
TRANSITIONS = {
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
            supplier_id VARCHAR(128) NOT NULL DEFAULT '',
            supplier_name VARCHAR(500) NOT NULL DEFAULT '',
            request_reference VARCHAR(255) NOT NULL DEFAULT '',
            document_date VARCHAR(32) NOT NULL DEFAULT '',
            currency VARCHAR(32) NOT NULL DEFAULT '',
            total_amount VARCHAR(64) NOT NULL DEFAULT '0',
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
    if document_type == "PURCHASE_EXCEL" and suffix not in {".xlsx", ".xlsm", ".xls"}:
        raise ValueError("PURCHASE_EXCEL requires .xlsx, .xlsm or .xls")
    if document_type == "PURCHASE_PDF" and suffix != ".pdf":
        raise ValueError("PURCHASE_PDF requires .pdf")
    if document_type == "PURCHASE_IMAGE" and suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("PURCHASE_IMAGE requires .png, .jpg, .jpeg or .webp")


def stage_document(
    db: Session,
    *,
    batch_id: str,
    document_type: str,
    original_name: str,
    source_reference: str,
    staged_by: str,
    content: bytes,
    content_type: str = "",
    supplier_id: str = "",
    supplier_name: str = "",
    request_reference: str = "",
    document_date: str = "",
    currency: str = "",
    total_amount: str = "0",
) -> dict[str, Any]:
    ensure_table(db)

    document_type = str(document_type or "").strip().upper()
    original_name = Path(str(original_name or "").strip()).name
    source_reference = str(source_reference or "").strip()
    staged_by = str(staged_by or "").strip()

    if document_type not in ALLOWED_TYPES:
        raise ValueError("Unsupported purchase document type")
    if not original_name or not source_reference or not staged_by or not content:
        raise ValueError(
            "original_name, source_reference, staged_by and content are required"
        )

    _validate_extension(document_type, original_name)
    digest = hashlib.sha256(content).hexdigest()

    existing = db.execute(text(f"""
        SELECT *
        FROM {STAGE_TABLE}
        WHERE batch_id=:batch_id
          AND document_type=:document_type
          AND sha256=:sha256
    """), {
        "batch_id": batch_id,
        "document_type": document_type,
        "sha256": digest,
    }).first()
    if existing:
        return {"status": "exists", "stage": _row(existing)}

    job_result = create_job(
        db,
        batch_id=batch_id,
        import_type=document_type,
        source_name=original_name,
        source_reference=source_reference,
        created_by=staged_by,
        message=f"{document_type} staged for purchase parser",
    )
    job = job_result["job"]

    if job_result["status"] == "created":
        job = update_job(
            db,
            job_id=job["id"],
            status="STAGED",
            operator=staged_by,
            message="Purchase request document safely staged",
        )

    stage_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    db.execute(text(f"""
        INSERT INTO {STAGE_TABLE} (
            id, batch_id, import_job_id, document_type,
            original_name, source_reference, content_type, file_size, sha256,
            supplier_id, supplier_name, request_reference,
            document_date, currency, total_amount,
            stage_status, parser_contract, validation_message,
            staged_by, staged_at, updated_by, updated_at
        ) VALUES (
            :id, :batch_id, :import_job_id, :document_type,
            :original_name, :source_reference, :content_type, :file_size, :sha256,
            :supplier_id, :supplier_name, :request_reference,
            :document_date, :currency, :total_amount,
            'STAGED', '', '',
            :staged_by, :staged_at, :staged_by, :updated_at
        )
    """), {
        "id": stage_id,
        "batch_id": batch_id,
        "import_job_id": job["id"],
        "document_type": document_type,
        "original_name": original_name,
        "source_reference": source_reference,
        "content_type": str(content_type or ""),
        "file_size": len(content),
        "sha256": digest,
        "supplier_id": str(supplier_id or ""),
        "supplier_name": str(supplier_name or ""),
        "request_reference": str(request_reference or ""),
        "document_date": str(document_date or ""),
        "currency": str(currency or ""),
        "total_amount": str(total_amount or "0"),
        "staged_by": staged_by,
        "staged_at": now,
        "updated_at": now,
    })
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {STAGE_TABLE} WHERE id=:id"),
        {"id": stage_id},
    ).first()
    return {"status": "staged", "stage": _row(row), "job": job}


def update_stage(
    db: Session,
    *,
    stage_id: str,
    stage_status: str,
    operator: str,
    parser_contract: str = "",
    validation_message: str = "",
) -> dict[str, Any]:
    ensure_table(db)

    current = db.execute(
        text(f"SELECT * FROM {STAGE_TABLE} WHERE id=:id"),
        {"id": stage_id},
    ).first()
    if not current:
        raise LookupError("Purchase request stage not found")

    record = _row(current)
    stage_status = str(stage_status or "").strip().upper()
    operator = str(operator or "").strip()

    if stage_status not in ALLOWED_STATUSES:
        raise ValueError("Unsupported stage status")
    if not operator:
        raise ValueError("operator is required")
    if (
        stage_status != record["stage_status"]
        and stage_status not in TRANSITIONS.get(record["stage_status"], set())
    ):
        raise ValueError(
            f"Invalid stage status transition: "
            f"{record['stage_status']} -> {stage_status}"
        )

    db.execute(text(f"""
        UPDATE {STAGE_TABLE}
        SET stage_status=:stage_status,
            parser_contract=:parser_contract,
            validation_message=:validation_message,
            updated_by=:operator,
            updated_at=:updated_at
        WHERE id=:id
    """), {
        "id": stage_id,
        "stage_status": stage_status,
        "parser_contract": str(
            parser_contract or record["parser_contract"] or ""
        ),
        "validation_message": str(
            validation_message or record["validation_message"] or ""
        ),
        "operator": operator,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    if stage_status == "ERROR":
        update_job(
            db,
            job_id=record["import_job_id"],
            status="PROCESSING",
            operator=operator,
            message="Purchase document validation started",
        )
        update_job(
            db,
            job_id=record["import_job_id"],
            status="ERROR",
            operator=operator,
            error_count=1,
            message=validation_message or "Purchase document validation failed",
        )
    elif stage_status == "READY":
        update_job(
            db,
            job_id=record["import_job_id"],
            status="PROCESSING",
            operator=operator,
            message="Purchase document validation completed",
        )
        update_job(
            db,
            job_id=record["import_job_id"],
            status="SUCCESS",
            operator=operator,
            success_count=1,
            message="Purchase document contract is ready",
        )

    db.commit()
    row = db.execute(
        text(f"SELECT * FROM {STAGE_TABLE} WHERE id=:id"),
        {"id": stage_id},
    ).first()
    return _row(row)


def list_stages(
    db: Session,
    *,
    batch_id: str = "",
    document_type: str = "",
    stage_status: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    ensure_table(db)

    clauses = []
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 1000)}

    if batch_id:
        clauses.append("batch_id=:batch_id")
        params["batch_id"] = batch_id

    if document_type:
        normalized = document_type.strip().upper()
        if normalized not in ALLOWED_TYPES:
            raise ValueError("Unsupported purchase document type")
        clauses.append("document_type=:document_type")
        params["document_type"] = normalized

    if stage_status:
        normalized = stage_status.strip().upper()
        if normalized not in ALLOWED_STATUSES:
            raise ValueError("Unsupported stage status")
        clauses.append("stage_status=:stage_status")
        params["stage_status"] = normalized

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(text(f"""
        SELECT *
        FROM {STAGE_TABLE}
        {where}
        ORDER BY staged_at DESC
        LIMIT :limit
    """), params).all()

    return [_row(row) for row in rows]


def summary(db: Session, batch_id: str = "") -> dict[str, Any]:
    rows = list_stages(db, batch_id=batch_id, limit=1000)
    return {
        "batch_id": batch_id,
        "stage_count": len(rows),
        "excel_count": sum(
            1 for row in rows if row["document_type"] == "PURCHASE_EXCEL"
        ),
        "pdf_count": sum(
            1 for row in rows if row["document_type"] == "PURCHASE_PDF"
        ),
        "image_count": sum(
            1 for row in rows if row["document_type"] == "PURCHASE_IMAGE"
        ),
        "ready_count": sum(
            1 for row in rows if row["stage_status"] == "READY"
        ),
        "error_count": sum(
            1 for row in rows if row["stage_status"] == "ERROR"
        ),
    }

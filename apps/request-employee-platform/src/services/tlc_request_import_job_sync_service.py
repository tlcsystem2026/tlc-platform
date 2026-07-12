from __future__ import annotations
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_batch_request_import_service import FILE_TABLE, ensure_tables as ensure_request_import_tables
from src.services.tlc_import_center_service import create_job, ensure_table as ensure_import_job_table, update_job


def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping if hasattr(row, "_mapping") else row)


def sync_request_files_to_import_jobs(db: Session, *, batch_id: str, operator: str) -> dict[str, Any]:
    ensure_request_import_tables(db)
    ensure_import_job_table(db)
    operator = str(operator or "").strip()
    if not operator:
        raise ValueError("operator is required")

    rows = db.execute(text(f"""
        SELECT * FROM {FILE_TABLE}
        WHERE batch_id=:batch_id
          AND file_type IN ('REQUEST_EXCEL','REQUEST_PDF')
        ORDER BY file_type, version_no
    """), {"batch_id": batch_id}).all()

    created = 0
    existing = 0
    synchronized = []
    for raw in rows:
        item = _row(raw)
        result = create_job(
            db,
            batch_id=batch_id,
            import_type=item["file_type"],
            source_name=item["original_name"],
            source_reference=f"batch-request-file:{item['id']}",
            created_by=operator,
            message=f"Auto-registered from Batch Request Import; version={item['version_no']}; active={bool(item['active'])}",
        )
        job = result["job"]
        if result["status"] == "created":
            created += 1
            job = update_job(db, job_id=job["id"], status="PROCESSING", operator=operator, record_count=1, message="Request file upload accepted")
            job = update_job(db, job_id=job["id"], status="SUCCESS", operator=operator, record_count=1, success_count=1, error_count=0, duplicate_count=0, message="Request file stored and registered successfully")
        else:
            existing += 1
        synchronized.append({
            "request_file_id": item["id"],
            "file_type": item["file_type"],
            "version_no": item["version_no"],
            "active": bool(item["active"]),
            "import_job_id": job["id"],
            "import_job_status": job["status"],
        })

    return {
        "batch_id": batch_id,
        "request_file_count": len(rows),
        "created_job_count": created,
        "existing_job_count": existing,
        "jobs": synchronized,
    }

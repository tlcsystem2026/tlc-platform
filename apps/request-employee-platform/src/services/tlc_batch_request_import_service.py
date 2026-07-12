from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_batch_service import (
    append_timeline,
    ensure_batch_tables,
    get_batch,
    transition_batch,
)

FILE_TABLE = "tlc_batch_import_file"
LOG_TABLE = "tlc_batch_import_log"
ALLOWED_TYPES = {"REQUEST_EXCEL", "REQUEST_PDF"}


def ensure_tables(db: Session) -> None:
    ensure_batch_tables(db)
    db.execute(text(f'''
        CREATE TABLE IF NOT EXISTS {FILE_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            batch_id VARCHAR(64) NOT NULL,
            file_type VARCHAR(64) NOT NULL,
            original_name VARCHAR(1000) NOT NULL,
            stored_name VARCHAR(1000) NOT NULL,
            storage_path VARCHAR(2000) NOT NULL,
            content_type VARCHAR(255) NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL,
            sha256 VARCHAR(64) NOT NULL,
            version_no INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            uploaded_by VARCHAR(255) NOT NULL,
            uploaded_at VARCHAR(64) NOT NULL,
            UNIQUE(batch_id, file_type, version_no),
            UNIQUE(batch_id, sha256)
        )
    '''))
    db.execute(text(f'''
        CREATE TABLE IF NOT EXISTS {LOG_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            batch_id VARCHAR(64) NOT NULL,
            operation VARCHAR(128) NOT NULL,
            file_id VARCHAR(64) NOT NULL DEFAULT '',
            file_type VARCHAR(64) NOT NULL DEFAULT '',
            original_name VARCHAR(1000) NOT NULL DEFAULT '',
            status VARCHAR(64) NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            operator VARCHAR(255) NOT NULL DEFAULT '',
            created_at VARCHAR(64) NOT NULL
        )
    '''))
    db.commit()


def _row(row: Any) -> dict[str, Any]:
    result = dict(row._mapping)
    if "active" in result:
        result["active"] = bool(result["active"])
    return result


def _root() -> Path:
    return Path(__file__).parents[2] / "data" / "batch_imports"


def _validate(file_type: str, name: str) -> None:
    suffix = Path(name).suffix.lower()
    if file_type == "REQUEST_EXCEL" and suffix not in {".xlsx", ".xlsm", ".xls"}:
        raise ValueError("REQUEST_EXCEL requires .xlsx, .xlsm or .xls")
    if file_type == "REQUEST_PDF" and suffix != ".pdf":
        raise ValueError("REQUEST_PDF requires .pdf")


def _log(db: Session, **kwargs: Any) -> None:
    data = {
        "id": uuid4().hex,
        "batch_id": kwargs["batch_id"],
        "operation": kwargs.get("operation", "UPLOAD_REQUEST_FILE"),
        "file_id": kwargs.get("file_id", ""),
        "file_type": kwargs.get("file_type", ""),
        "original_name": kwargs.get("original_name", ""),
        "status": kwargs["status"],
        "message": kwargs.get("message", ""),
        "operator": kwargs.get("operator", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.execute(text(f'''
        INSERT INTO {LOG_TABLE} (
            id,batch_id,operation,file_id,file_type,original_name,
            status,message,operator,created_at
        ) VALUES (
            :id,:batch_id,:operation,:file_id,:file_type,:original_name,
            :status,:message,:operator,:created_at
        )
    '''), data)


def upload_file(
    db: Session,
    *,
    batch_id: str,
    file_type: str,
    original_name: str,
    content_type: str,
    content: bytes,
    uploaded_by: str,
) -> dict[str, Any]:
    ensure_tables(db)
    batch = get_batch(db, batch_id)
    if batch is None:
        raise LookupError("Batch not found")
    if batch["status"] == "FINISHED":
        raise ValueError("Finished batch cannot accept files")

    file_type = str(file_type or "").strip().upper()
    original_name = Path(str(original_name or "").strip()).name
    uploaded_by = str(uploaded_by or "").strip()
    if file_type not in ALLOWED_TYPES:
        raise ValueError("Unsupported request file type")
    if not original_name or not uploaded_by or not content:
        raise ValueError("original_name, uploaded_by and file content are required")
    _validate(file_type, original_name)

    digest = hashlib.sha256(content).hexdigest()
    duplicate = db.execute(text(f'''
        SELECT * FROM {FILE_TABLE}
        WHERE batch_id=:batch_id AND sha256=:sha256
    '''), {"batch_id": batch_id, "sha256": digest}).first()
    if duplicate:
        record = _row(duplicate)
        _log(
            db, batch_id=batch_id, status="DUPLICATE",
            operator=uploaded_by, file_id=record["id"],
            file_type=file_type, original_name=original_name,
            message="Duplicate content ignored"
        )
        db.commit()
        return {"status": "duplicate", "file": record}

    version = int(db.execute(text(f'''
        SELECT COALESCE(MAX(version_no),0)
        FROM {FILE_TABLE}
        WHERE batch_id=:batch_id AND file_type=:file_type
    '''), {"batch_id": batch_id, "file_type": file_type}).scalar() or 0) + 1

    db.execute(text(f'''
        UPDATE {FILE_TABLE} SET active=0
        WHERE batch_id=:batch_id AND file_type=:file_type
    '''), {"batch_id": batch_id, "file_type": file_type})

    suffix = Path(original_name).suffix.lower()
    stored_name = f"{file_type.lower()}_v{version:03d}_{digest[:12]}{suffix}"
    folder = _root() / batch["batch_no"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / stored_name
    path.write_bytes(content)

    file_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    db.execute(text(f'''
        INSERT INTO {FILE_TABLE} (
            id,batch_id,file_type,original_name,stored_name,storage_path,
            content_type,file_size,sha256,version_no,active,uploaded_by,uploaded_at
        ) VALUES (
            :id,:batch_id,:file_type,:original_name,:stored_name,:storage_path,
            :content_type,:file_size,:sha256,:version_no,1,:uploaded_by,:uploaded_at
        )
    '''), {
        "id": file_id, "batch_id": batch_id, "file_type": file_type,
        "original_name": original_name, "stored_name": stored_name,
        "storage_path": str(path), "content_type": content_type,
        "file_size": len(content), "sha256": digest, "version_no": version,
        "uploaded_by": uploaded_by, "uploaded_at": now,
    })
    _log(
        db, batch_id=batch_id, status="SUCCESS", operator=uploaded_by,
        file_id=file_id, file_type=file_type, original_name=original_name,
        message=f"{file_type} version {version} uploaded"
    )
    append_timeline(
        db, batch_id=batch_id, event_type="REQUEST_FILE_UPLOADED",
        old_status=batch["status"], new_status=batch["status"],
        message=f"{file_type} v{version}: {original_name}",
        operator=uploaded_by,
    )
    db.commit()

    if batch["status"] == "NEW":
        transition_batch(
            db, batch_id, new_status="IMPORTING",
            operator=uploaded_by, message="First request file uploaded"
        )

    row = db.execute(
        text(f"SELECT * FROM {FILE_TABLE} WHERE id=:id"),
        {"id": file_id},
    ).first()
    return {"status": "uploaded", "file": _row(row)}


def list_files(db: Session, batch_id: str, include_inactive: bool = True):
    ensure_tables(db)
    if get_batch(db, batch_id) is None:
        raise LookupError("Batch not found")
    where = "batch_id=:batch_id" + ("" if include_inactive else " AND active=1")
    rows = db.execute(text(f'''
        SELECT * FROM {FILE_TABLE}
        WHERE {where}
        ORDER BY file_type, version_no DESC
    '''), {"batch_id": batch_id}).all()
    return [_row(row) for row in rows]


def readiness(db: Session, batch_id: str):
    files = list_files(db, batch_id, include_inactive=False)
    types = {item["file_type"] for item in files}
    missing = [item for item in ("REQUEST_EXCEL", "REQUEST_PDF") if item not in types]
    return {
        "batch_id": batch_id,
        "ready_for_compare": not missing,
        "missing_file_types": missing,
        "active_files": files,
    }


def list_logs(db: Session, batch_id: str, limit: int = 500):
    ensure_tables(db)
    if get_batch(db, batch_id) is None:
        raise LookupError("Batch not found")
    rows = db.execute(text(f'''
        SELECT * FROM {LOG_TABLE}
        WHERE batch_id=:batch_id
        ORDER BY created_at DESC
        LIMIT :limit
    '''), {"batch_id": batch_id, "limit": min(max(limit,1),1000)}).all()
    return [_row(row) for row in rows]

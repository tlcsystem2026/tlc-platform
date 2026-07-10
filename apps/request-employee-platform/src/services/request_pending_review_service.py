from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session

TABLE_NAME = "request_pending_review"

def ensure_pending_review_table(db: Session) -> None:
    db.execute(text(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id VARCHAR(64) PRIMARY KEY,
        request_no VARCHAR(255) NOT NULL UNIQUE,
        request_date VARCHAR(64) NOT NULL DEFAULT '',
        customer_id VARCHAR(255) NOT NULL DEFAULT '',
        customer_name VARCHAR(500) NOT NULL DEFAULT '',
        currency VARCHAR(16) NOT NULL DEFAULT '',
        subtotal VARCHAR(64) NOT NULL DEFAULT '',
        tax_amount VARCHAR(64) NOT NULL DEFAULT '',
        total_amount VARCHAR(64) NOT NULL DEFAULT '',
        excel_source VARCHAR(1000) NOT NULL DEFAULT '',
        pdf_source VARCHAR(1000) NOT NULL DEFAULT '',
        compare_summary TEXT NOT NULL DEFAULT '{{}}',
        request_payload TEXT NOT NULL DEFAULT '{{}}',
        status VARCHAR(64) NOT NULL DEFAULT 'PENDING_REVIEW',
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    )"""))
    db.commit()

def _row_to_dict(row: Any) -> dict[str, Any]:
    result = dict(row._mapping if hasattr(row, "_mapping") else row)
    for key in ("compare_summary", "request_payload"):
        try: result[key] = json.loads(result.get(key) or "{}")
        except Exception: result[key] = {}
    return result

def create_pending_review(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_pending_review_table(db)
    if not bool(payload.get("matched", False)):
        raise ValueError("Only matched request documents can enter pending review")
    request_no = str(payload.get("request_no", "") or "").strip()
    if not request_no:
        raise ValueError("request_no is required")
    existing = db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE request_no=:request_no"), {"request_no": request_no}).first()
    if existing:
        return {"status": "exists", "record": _row_to_dict(existing)}
    doc = payload.get("request_document") or {}
    sources = payload.get("sources") or {}
    now = datetime.now(timezone.utc).isoformat()
    params = {
        "id": uuid4().hex, "request_no": request_no,
        "request_date": str(doc.get("request_date", "") or ""),
        "customer_id": str(doc.get("customer_id", "") or ""),
        "customer_name": str(doc.get("customer_name", "") or ""),
        "currency": str(doc.get("currency", "") or ""),
        "subtotal": str(doc.get("subtotal", "") or ""),
        "tax_amount": str(doc.get("tax_amount", "") or ""),
        "total_amount": str(doc.get("total_amount", "") or ""),
        "excel_source": str(sources.get("excel", "") or ""),
        "pdf_source": str(sources.get("pdf", "") or ""),
        "compare_summary": json.dumps({"matched": True, "difference_count": int(payload.get("difference_count", 0) or 0)}, ensure_ascii=False),
        "request_payload": json.dumps(doc, ensure_ascii=False),
        "status": "PENDING_REVIEW", "created_at": now, "updated_at": now,
    }
    db.execute(text(f"""
    INSERT INTO {TABLE_NAME} (
      id,request_no,request_date,customer_id,customer_name,currency,
      subtotal,tax_amount,total_amount,excel_source,pdf_source,
      compare_summary,request_payload,status,created_at,updated_at
    ) VALUES (
      :id,:request_no,:request_date,:customer_id,:customer_name,:currency,
      :subtotal,:tax_amount,:total_amount,:excel_source,:pdf_source,
      :compare_summary,:request_payload,:status,:created_at,:updated_at
    )"""), params)
    db.commit()
    row = db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"), {"id": params["id"]}).first()
    return {"status": "created", "record": _row_to_dict(row)}

def list_pending_reviews(db: Session, *, status: str = "", limit: int = 200) -> list[dict[str, Any]]:
    ensure_pending_review_table(db)
    limit = min(max(int(limit), 1), 1000)
    if status:
        rows = db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE status=:status ORDER BY created_at DESC LIMIT :limit"), {"status": status, "limit": limit}).all()
    else:
        rows = db.execute(text(f"SELECT * FROM {TABLE_NAME} ORDER BY created_at DESC LIMIT :limit"), {"limit": limit}).all()
    return [_row_to_dict(row) for row in rows]

def get_pending_review(db: Session, record_id: str) -> dict[str, Any] | None:
    ensure_pending_review_table(db)
    row = db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"), {"id": record_id}).first()
    return _row_to_dict(row) if row else None

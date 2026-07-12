from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_batch_compare_service import latest_batch_compare
from src.services.tlc_batch_service import append_timeline, get_batch, transition_batch

TABLE_NAME = "tlc_batch_review_link"
ALLOWED = {"PENDING","APPROVED","REJECTED","CANCELLED","POSTED"}

def ensure_table(db: Session) -> None:
    db.execute(text(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME}(
      id VARCHAR(64) PRIMARY KEY,
      batch_id VARCHAR(64) NOT NULL,
      compare_result_id VARCHAR(64) NOT NULL,
      pending_review_id VARCHAR(128) NOT NULL,
      request_no VARCHAR(255) NOT NULL DEFAULT '',
      review_status VARCHAR(64) NOT NULL DEFAULT 'PENDING',
      linked_by VARCHAR(255) NOT NULL,
      linked_at VARCHAR(64) NOT NULL,
      updated_by VARCHAR(255) NOT NULL DEFAULT '',
      updated_at VARCHAR(64) NOT NULL,
      note TEXT NOT NULL DEFAULT '',
      UNIQUE(batch_id,pending_review_id),
      UNIQUE(batch_id,compare_result_id)
    )"""))
    db.commit()

def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping)

def get_review_payload(db: Session, batch_id: str) -> dict[str, Any]:
    result = latest_batch_compare(db, batch_id)
    if result is None:
        raise ValueError("No compare result found")
    if not result["matched"]:
        raise ValueError("Latest compare result is not matched")
    payload = dict(result.get("result") or {})
    payload.setdefault("matched", True)
    payload.setdefault("request_no", result["request_no"])
    payload.setdefault("difference_count", result["difference_count"])
    payload["_batch_context"] = {
        "batch_id": batch_id,
        "compare_result_id": result["id"],
    }
    return payload

def create_link(db: Session, *, batch_id: str, pending_review_id: str, linked_by: str, note: str=""):
    ensure_table(db)
    batch = get_batch(db, batch_id)
    if not batch:
        raise LookupError("Batch not found")
    if batch["status"] not in {"READY_REVIEW","REVIEWING"}:
        raise ValueError("Batch must be READY_REVIEW or REVIEWING")
    compare = latest_batch_compare(db, batch_id)
    if not compare or not compare["matched"]:
        raise ValueError("Matched compare result is required")
    pending_review_id = str(pending_review_id or "").strip()
    linked_by = str(linked_by or "").strip()
    if not pending_review_id:
        raise ValueError("pending_review_id is required")
    if not linked_by:
        raise ValueError("linked_by is required")
    existing = db.execute(text(f"""
      SELECT * FROM {TABLE_NAME}
      WHERE batch_id=:b AND (pending_review_id=:p OR compare_result_id=:c)
      LIMIT 1
    """), {"b":batch_id,"p":pending_review_id,"c":compare["id"]}).first()
    if existing:
        return {"status":"exists","review_link":_row(existing)}
    now = datetime.now(timezone.utc).isoformat()
    rid = uuid4().hex
    db.execute(text(f"""
      INSERT INTO {TABLE_NAME}(
       id,batch_id,compare_result_id,pending_review_id,request_no,review_status,
       linked_by,linked_at,updated_by,updated_at,note
      ) VALUES(:id,:b,:c,:p,:r,'PENDING',:u,:t,:u,:t,:n)
    """), {"id":rid,"b":batch_id,"c":compare["id"],"p":pending_review_id,
           "r":compare["request_no"],"u":linked_by,"t":now,"n":str(note or "")})
    append_timeline(db,batch_id=batch_id,event_type="PENDING_REVIEW_CREATED",
      old_status=batch["status"],new_status=batch["status"],
      message=f"Pending review linked: {pending_review_id}",operator=linked_by)
    db.commit()
    if batch["status"]=="READY_REVIEW":
        transition_batch(db,batch_id,new_status="REVIEWING",operator=linked_by,
          message="Matched request entered Pending Review")
    row=db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),{"id":rid}).first()
    return {"status":"linked","review_link":_row(row)}

def list_links(db: Session, batch_id: str):
    ensure_table(db)
    if not get_batch(db,batch_id):
        raise LookupError("Batch not found")
    rows=db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE batch_id=:b ORDER BY linked_at DESC"),
                    {"b":batch_id}).all()
    return [_row(x) for x in rows]

def update_link(db: Session, *, batch_id: str, link_id: str, review_status: str, operator: str, note: str=""):
    ensure_table(db)
    review_status=str(review_status or "").strip().upper()
    operator=str(operator or "").strip()
    if review_status not in ALLOWED:
        raise ValueError("Unsupported review status")
    if not operator:
        raise ValueError("operator is required")
    current=db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id AND batch_id=:b"),
                       {"id":link_id,"b":batch_id}).first()
    if not current:
        raise LookupError("Batch review link not found")
    now=datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""UPDATE {TABLE_NAME}
      SET review_status=:s,updated_by=:u,updated_at=:t,note=:n WHERE id=:id"""),
      {"s":review_status,"u":operator,"t":now,"n":str(note or current._mapping["note"] or ""),"id":link_id})
    batch=get_batch(db,batch_id)
    append_timeline(db,batch_id=batch_id,event_type="BATCH_REVIEW_STATUS_CHANGED",
      old_status=batch["status"],new_status=batch["status"],
      message=f"Review status: {review_status}",operator=operator)
    db.commit()
    if review_status=="POSTED":
        batch=get_batch(db,batch_id)
        if batch and batch["status"]=="REVIEWING":
            transition_batch(db,batch_id,new_status="LEDGER_POSTED",operator=operator,
              message="Approved request posted to formal Sales Ledger")
    row=db.execute(text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),{"id":link_id}).first()
    return _row(row)

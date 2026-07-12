from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_batch_review_service import (
    TABLE_NAME as REVIEW_LINK_TABLE,
    ensure_table as ensure_review_table,
)
from src.services.tlc_batch_service import append_timeline, get_batch, transition_batch

TABLE_NAME = "tlc_batch_sales_ledger_link"


def ensure_table(db: Session) -> None:
    ensure_review_table(db)
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id VARCHAR(64) PRIMARY KEY,
            batch_id VARCHAR(64) NOT NULL,
            review_link_id VARCHAR(64) NOT NULL,
            pending_review_id VARCHAR(128) NOT NULL,
            sales_ledger_id VARCHAR(128) NOT NULL,
            request_no VARCHAR(255) NOT NULL DEFAULT '',
            posted_by VARCHAR(255) NOT NULL,
            posted_at VARCHAR(64) NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            UNIQUE(batch_id, sales_ledger_id),
            UNIQUE(batch_id, review_link_id)
        )
    """))
    db.commit()


def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping if hasattr(row, "_mapping") else row)


def create_ledger_link(
    db: Session,
    *,
    batch_id: str,
    review_link_id: str,
    sales_ledger_id: str,
    posted_by: str,
    note: str = "",
) -> dict[str, Any]:
    ensure_table(db)
    batch = get_batch(db, batch_id)
    if batch is None:
        raise LookupError("Batch not found")
    if batch["status"] not in {"REVIEWING", "LEDGER_POSTED"}:
        raise ValueError("Batch must be REVIEWING or LEDGER_POSTED")

    review_link_id = str(review_link_id or "").strip()
    sales_ledger_id = str(sales_ledger_id or "").strip()
    posted_by = str(posted_by or "").strip()
    if not review_link_id:
        raise ValueError("review_link_id is required")
    if not sales_ledger_id:
        raise ValueError("sales_ledger_id is required")
    if not posted_by:
        raise ValueError("posted_by is required")

    review = db.execute(text(f"""
        SELECT * FROM {REVIEW_LINK_TABLE}
        WHERE id=:id AND batch_id=:batch_id
    """), {"id": review_link_id, "batch_id": batch_id}).first()
    if not review:
        raise LookupError("Batch review link not found")

    existing = db.execute(text(f"""
        SELECT * FROM {TABLE_NAME}
        WHERE batch_id=:batch_id
          AND (review_link_id=:review_link_id OR sales_ledger_id=:sales_ledger_id)
        LIMIT 1
    """), {
        "batch_id": batch_id,
        "review_link_id": review_link_id,
        "sales_ledger_id": sales_ledger_id,
    }).first()
    if existing:
        return {"status": "exists", "ledger_link": _row(existing)}

    now = datetime.now(timezone.utc).isoformat()
    record_id = uuid4().hex
    db.execute(text(f"""
        INSERT INTO {TABLE_NAME} (
            id, batch_id, review_link_id, pending_review_id,
            sales_ledger_id, request_no, posted_by, posted_at, note
        ) VALUES (
            :id, :batch_id, :review_link_id, :pending_review_id,
            :sales_ledger_id, :request_no, :posted_by, :posted_at, :note
        )
    """), {
        "id": record_id,
        "batch_id": batch_id,
        "review_link_id": review_link_id,
        "pending_review_id": str(review._mapping["pending_review_id"]),
        "sales_ledger_id": sales_ledger_id,
        "request_no": str(review._mapping["request_no"] or ""),
        "posted_by": posted_by,
        "posted_at": now,
        "note": str(note or ""),
    })

    db.execute(text(f"""
        UPDATE {REVIEW_LINK_TABLE}
        SET review_status='POSTED',
            updated_by=:operator,
            updated_at=:updated_at,
            note=:note
        WHERE id=:id
    """), {
        "operator": posted_by,
        "updated_at": now,
        "note": str(note or review._mapping["note"] or ""),
        "id": review_link_id,
    })

    append_timeline(
        db,
        batch_id=batch_id,
        event_type="SALES_LEDGER_LINKED",
        old_status=batch["status"],
        new_status=batch["status"],
        message=f"Sales Ledger linked: {sales_ledger_id}",
        operator=posted_by,
    )
    db.commit()

    if batch["status"] == "REVIEWING":
        transition_batch(
            db,
            batch_id,
            new_status="LEDGER_POSTED",
            operator=posted_by,
            message="Request posted to formal Sales Ledger",
        )

    row = db.execute(
        text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),
        {"id": record_id},
    ).first()
    return {"status": "linked", "ledger_link": _row(row)}


def list_ledger_links(db: Session, batch_id: str) -> list[dict[str, Any]]:
    ensure_table(db)
    if get_batch(db, batch_id) is None:
        raise LookupError("Batch not found")
    rows = db.execute(text(f"""
        SELECT * FROM {TABLE_NAME}
        WHERE batch_id=:batch_id
        ORDER BY posted_at DESC
    """), {"batch_id": batch_id}).all()
    return [_row(row) for row in rows]


def ledger_summary(db: Session, batch_id: str) -> dict[str, Any]:
    links = list_ledger_links(db, batch_id)
    return {
        "batch_id": batch_id,
        "ledger_count": len(links),
        "request_nos": [item["request_no"] for item in links],
        "sales_ledger_ids": [item["sales_ledger_id"] for item in links],
        "latest_posted_at": links[0]["posted_at"] if links else "",
    }

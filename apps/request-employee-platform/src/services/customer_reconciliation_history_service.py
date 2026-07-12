from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.customer_period_reconciliation_service import (
    customer_period_reconciliation,
)


TABLE_NAME = "customer_payment_reconciliation_history"


def _decimal(value: Any) -> Decimal:
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return Decimal("0")
    try:
        return Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"Invalid amount: {value}")


def _money(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return format(normalized.quantize(Decimal("1")), "f")
    return format(normalized, "f")


def ensure_reconciliation_history_table(db: Session) -> None:
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id VARCHAR(64) PRIMARY KEY,
            customer_id VARCHAR(128) NOT NULL,
            customer_name VARCHAR(500) NOT NULL DEFAULT '',
            previous_request_cutoff VARCHAR(32) NOT NULL,
            current_request_cutoff VARCHAR(32) NOT NULL,
            previous_bank_cutoff VARCHAR(32) NOT NULL,
            current_bank_cutoff VARCHAR(32) NOT NULL,
            opening_outstanding VARCHAR(64) NOT NULL DEFAULT '0',
            period_sales_total VARCHAR(64) NOT NULL DEFAULT '0',
            period_payment_total VARCHAR(64) NOT NULL DEFAULT '0',
            closing_outstanding VARCHAR(64) NOT NULL DEFAULT '0',
            status VARCHAR(64) NOT NULL,
            sales_count INTEGER NOT NULL DEFAULT 0,
            payment_count INTEGER NOT NULL DEFAULT 0,
            result_json TEXT NOT NULL DEFAULT '{{}}',
            confirmed_by VARCHAR(255) NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            confirmed_at VARCHAR(64) NOT NULL,
            created_at VARCHAR(64) NOT NULL,
            UNIQUE(
                customer_id,
                previous_request_cutoff,
                current_request_cutoff,
                previous_bank_cutoff,
                current_bank_cutoff
            )
        )
    """))
    db.commit()


def _row(row: Any) -> dict[str, Any]:
    result = dict(row._mapping if hasattr(row, "_mapping") else row)
    try:
        result["result"] = json.loads(result.pop("result_json") or "{}")
    except Exception:
        result["result"] = {}
    return result


def get_latest_reconciliation(
    db: Session,
    customer_id: str,
) -> dict[str, Any] | None:
    ensure_reconciliation_history_table(db)
    row = db.execute(text(f"""
        SELECT *
        FROM {TABLE_NAME}
        WHERE customer_id = :customer_id
        ORDER BY confirmed_at DESC
        LIMIT 1
    """), {"customer_id": customer_id}).first()
    return _row(row) if row else None


def calculate_reconciliation_with_carry_forward(
    db: Session,
    *,
    customer_id: str,
    previous_request_cutoff: str,
    current_request_cutoff: str,
    previous_bank_cutoff: str,
    current_bank_cutoff: str,
    opening_outstanding: str | None = None,
) -> dict[str, Any]:
    latest = get_latest_reconciliation(db, customer_id)

    if opening_outstanding is None or str(opening_outstanding).strip() == "":
        opening = _decimal(
            latest["closing_outstanding"] if latest else "0"
        )
    else:
        opening = _decimal(opening_outstanding)

    period = customer_period_reconciliation(
        db,
        customer_id=customer_id,
        previous_request_cutoff=previous_request_cutoff,
        current_request_cutoff=current_request_cutoff,
        previous_bank_cutoff=previous_bank_cutoff,
        current_bank_cutoff=current_bank_cutoff,
    )

    sales_total = _decimal(period["sales_total"])
    payment_total = _decimal(period["payment_total"])
    closing = opening + sales_total - payment_total

    if closing == 0:
        status = "SETTLED"
    elif closing > 0 and payment_total == 0 and sales_total > 0:
        status = "UNPAID"
    elif closing > 0:
        status = "PARTIAL"
    else:
        status = "OVERPAID"

    return {
        **period,
        "opening_outstanding": _money(opening),
        "closing_outstanding": _money(closing),
        "status": status,
        "carry_forward_source": (
            {
                "reconciliation_id": latest["id"],
                "closing_outstanding": latest["closing_outstanding"],
                "current_request_cutoff": latest["current_request_cutoff"],
                "current_bank_cutoff": latest["current_bank_cutoff"],
            }
            if latest
            else None
        ),
    }


def save_reconciliation(
    db: Session,
    payload: dict[str, Any],
) -> dict[str, Any]:
    ensure_reconciliation_history_table(db)

    customer_id = str(payload.get("customer_id", "") or "").strip()
    confirmed_by = str(payload.get("confirmed_by", "") or "").strip()

    if not customer_id:
        raise ValueError("customer_id is required")
    if not confirmed_by:
        raise ValueError("confirmed_by is required")

    previous_request_cutoff = str(payload.get("previous_request_cutoff", "") or "").strip()
    current_request_cutoff = str(payload.get("current_request_cutoff", "") or "").strip()
    previous_bank_cutoff = str(payload.get("previous_bank_cutoff", "") or "").strip()
    current_bank_cutoff = str(payload.get("current_bank_cutoff", "") or "").strip()

    calculated = calculate_reconciliation_with_carry_forward(
        db,
        customer_id=customer_id,
        previous_request_cutoff=previous_request_cutoff,
        current_request_cutoff=current_request_cutoff,
        previous_bank_cutoff=previous_bank_cutoff,
        current_bank_cutoff=current_bank_cutoff,
        opening_outstanding=payload.get("opening_outstanding"),
    )

    existing = db.execute(text(f"""
        SELECT *
        FROM {TABLE_NAME}
        WHERE customer_id = :customer_id
          AND previous_request_cutoff = :previous_request_cutoff
          AND current_request_cutoff = :current_request_cutoff
          AND previous_bank_cutoff = :previous_bank_cutoff
          AND current_bank_cutoff = :current_bank_cutoff
    """), {
        "customer_id": customer_id,
        "previous_request_cutoff": previous_request_cutoff,
        "current_request_cutoff": current_request_cutoff,
        "previous_bank_cutoff": previous_bank_cutoff,
        "current_bank_cutoff": current_bank_cutoff,
    }).first()

    if existing:
        return {
            "status": "exists",
            "record": _row(existing),
            "calculated": calculated,
        }

    now = datetime.now(timezone.utc).isoformat()
    record_id = uuid4().hex

    params = {
        "id": record_id,
        "customer_id": customer_id,
        "customer_name": calculated.get("customer_name", ""),
        "previous_request_cutoff": previous_request_cutoff,
        "current_request_cutoff": current_request_cutoff,
        "previous_bank_cutoff": previous_bank_cutoff,
        "current_bank_cutoff": current_bank_cutoff,
        "opening_outstanding": calculated["opening_outstanding"],
        "period_sales_total": calculated["sales_total"],
        "period_payment_total": calculated["payment_total"],
        "closing_outstanding": calculated["closing_outstanding"],
        "status": calculated["status"],
        "sales_count": calculated["sales_count"],
        "payment_count": calculated["payment_count"],
        "result_json": json.dumps(calculated, ensure_ascii=False),
        "confirmed_by": confirmed_by,
        "note": str(payload.get("note", "") or ""),
        "confirmed_at": now,
        "created_at": now,
    }

    db.execute(text(f"""
        INSERT INTO {TABLE_NAME} (
            id, customer_id, customer_name,
            previous_request_cutoff, current_request_cutoff,
            previous_bank_cutoff, current_bank_cutoff,
            opening_outstanding, period_sales_total,
            period_payment_total, closing_outstanding,
            status, sales_count, payment_count,
            result_json, confirmed_by, note,
            confirmed_at, created_at
        ) VALUES (
            :id, :customer_id, :customer_name,
            :previous_request_cutoff, :current_request_cutoff,
            :previous_bank_cutoff, :current_bank_cutoff,
            :opening_outstanding, :period_sales_total,
            :period_payment_total, :closing_outstanding,
            :status, :sales_count, :payment_count,
            :result_json, :confirmed_by, :note,
            :confirmed_at, :created_at
        )
    """), params)
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),
        {"id": record_id},
    ).first()

    return {
        "status": "saved",
        "record": _row(row),
        "calculated": calculated,
    }


def list_reconciliations(
    db: Session,
    *,
    customer_id: str = "",
    limit: int = 200,
) -> list[dict[str, Any]]:
    ensure_reconciliation_history_table(db)

    safe_limit = min(max(int(limit), 1), 1000)
    if customer_id:
        rows = db.execute(text(f"""
            SELECT *
            FROM {TABLE_NAME}
            WHERE customer_id = :customer_id
            ORDER BY confirmed_at DESC
            LIMIT :limit
        """), {
            "customer_id": customer_id,
            "limit": safe_limit,
        }).all()
    else:
        rows = db.execute(text(f"""
            SELECT *
            FROM {TABLE_NAME}
            ORDER BY confirmed_at DESC
            LIMIT :limit
        """), {"limit": safe_limit}).all()

    return [_row(row) for row in rows]

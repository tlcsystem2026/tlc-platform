
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_sales_ledger_evidence_service import list_sales_evidence
from src.services.tlc_bank_payment_evidence_service import list_bank_payment_evidence
from src.services.tlc_customer_reconciliation_case_service import ensure_tables as ensure_reconciliation_tables


MATCH_TABLE = "tlc_customer_auto_match"
AUDIT_TABLE = "tlc_customer_auto_match_audit"

ALLOWED_STATUSES = {"PROPOSED", "MATCHED", "REJECTED", "CANCELLED"}


def ensure_tables(db: Session) -> None:
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {MATCH_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            reconciliation_id VARCHAR(64) NOT NULL,
            snapshot_id VARCHAR(64) NOT NULL,
            customer_id VARCHAR(255) NOT NULL,
            customer_name VARCHAR(500) NOT NULL DEFAULT '',
            sales_record_id VARCHAR(255) NOT NULL DEFAULT '',
            payment_record_id VARCHAR(255) NOT NULL DEFAULT '',
            sales_document_no VARCHAR(255) NOT NULL DEFAULT '',
            payment_reference_no VARCHAR(255) NOT NULL DEFAULT '',
            sales_date VARCHAR(32) NOT NULL DEFAULT '',
            payment_date VARCHAR(32) NOT NULL DEFAULT '',
            sales_amount VARCHAR(64) NOT NULL DEFAULT '0',
            payment_amount VARCHAR(64) NOT NULL DEFAULT '0',
            difference_amount VARCHAR(64) NOT NULL DEFAULT '0',
            match_rule VARCHAR(128) NOT NULL,
            match_score INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(64) NOT NULL DEFAULT 'PROPOSED',
            created_by VARCHAR(255) NOT NULL,
            created_at VARCHAR(64) NOT NULL,
            confirmed_by VARCHAR(255) NOT NULL DEFAULT '',
            confirmed_at VARCHAR(64) NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            UNIQUE(reconciliation_id, sales_record_id, payment_record_id)
        )
    """))
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            auto_match_id VARCHAR(64) NOT NULL,
            reconciliation_id VARCHAR(64) NOT NULL,
            event_type VARCHAR(128) NOT NULL,
            actor VARCHAR(255) NOT NULL,
            event_at VARCHAR(64) NOT NULL,
            old_status VARCHAR(64) NOT NULL DEFAULT '',
            new_status VARCHAR(64) NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT ''
        )
    """))
    db.commit()


def _row(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0").replace(",", ""))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _fmt(value: Decimal) -> str:
    value = value.quantize(Decimal("0.01"))
    s = format(value, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def _audit(
    db: Session,
    *,
    auto_match_id: str,
    reconciliation_id: str,
    event_type: str,
    actor: str,
    old_status: str = "",
    new_status: str = "",
    message: str = "",
) -> None:
    db.execute(text(f"""
        INSERT INTO {AUDIT_TABLE} (
            id, auto_match_id, reconciliation_id,
            event_type, actor, event_at,
            old_status, new_status, message
        ) VALUES (
            :id, :auto_match_id, :reconciliation_id,
            :event_type, :actor, :event_at,
            :old_status, :new_status, :message
        )
    """), {
        "id": uuid4().hex,
        "auto_match_id": auto_match_id,
        "reconciliation_id": reconciliation_id,
        "event_type": event_type,
        "actor": actor,
        "event_at": datetime.now(timezone.utc).isoformat(),
        "old_status": old_status,
        "new_status": new_status,
        "message": message,
    })


def _get_case(db: Session, reconciliation_id: str) -> dict[str, Any]:
    ensure_reconciliation_tables(db)
    row = db.execute(
        text(
            "SELECT * FROM tlc_customer_reconciliation_case "
            "WHERE id=:id"
        ),
        {"id": reconciliation_id},
    ).first()
    if not row:
        raise LookupError("Reconciliation case not found")
    return _row(row)


def _record_id(record: dict[str, Any], fallback_prefix: str, index: int) -> str:
    value = str(record.get("id") or "").strip()
    return value or f"{fallback_prefix}-{index}"


def generate_auto_matches(
    db: Session,
    *,
    reconciliation_id: str,
    operator: str,
) -> dict[str, Any]:
    ensure_tables(db)

    reconciliation_id = str(reconciliation_id or "").strip()
    operator = str(operator or "").strip()
    if not reconciliation_id:
        raise ValueError("reconciliation_id is required")
    if not operator:
        raise ValueError("operator is required")

    case = _get_case(db, reconciliation_id)
    if case["status"] == "CANCELLED":
        raise ValueError("Cancelled reconciliation cannot be auto matched")

    sales = list_sales_evidence(
        db,
        customer_id=case["customer_id"],
        customer_name=case.get("customer_name", ""),
        previous_cutoff=case["previous_request_cutoff"],
        current_cutoff=case["current_request_cutoff"],
        limit=5000,
    )
    payments = list_bank_payment_evidence(
        db,
        customer_id=case["customer_id"],
        customer_name=case.get("customer_name", ""),
        previous_cutoff=case["previous_bank_cutoff"],
        current_cutoff=case["current_bank_cutoff"],
        limit=5000,
    )

    used_payments: set[str] = set()
    created = 0
    existing = 0
    proposals = []

    for s_index, sales_record in enumerate(sales["records"]):
        sales_id = _record_id(sales_record, "SALES", s_index)
        sales_amount = _decimal(sales_record.get("amount"))
        if sales_amount <= 0:
            continue

        candidates = []
        for p_index, payment_record in enumerate(payments["records"]):
            payment_id = _record_id(payment_record, "PAYMENT", p_index)
            if payment_id in used_payments:
                continue

            payment_amount = _decimal(payment_record.get("amount"))
            if payment_amount <= 0:
                continue

            difference = sales_amount - payment_amount
            if difference == 0:
                candidates.append((
                    100,
                    payment_id,
                    payment_record,
                    "EXACT_AMOUNT",
                    difference,
                ))

        if not candidates:
            continue

        candidates.sort(key=lambda item: (-item[0], str(item[2].get("business_date", ""))))
        score, payment_id, payment_record, rule, difference = candidates[0]

        found = db.execute(text(f"""
            SELECT * FROM {MATCH_TABLE}
            WHERE reconciliation_id=:reconciliation_id
              AND sales_record_id=:sales_record_id
              AND payment_record_id=:payment_record_id
        """), {
            "reconciliation_id": reconciliation_id,
            "sales_record_id": sales_id,
            "payment_record_id": payment_id,
        }).first()

        if found:
            existing += 1
            proposals.append(_row(found))
            used_payments.add(payment_id)
            continue

        match_id = uuid4().hex
        now = datetime.now(timezone.utc).isoformat()

        db.execute(text(f"""
            INSERT INTO {MATCH_TABLE} (
                id, reconciliation_id, snapshot_id,
                customer_id, customer_name,
                sales_record_id, payment_record_id,
                sales_document_no, payment_reference_no,
                sales_date, payment_date,
                sales_amount, payment_amount, difference_amount,
                match_rule, match_score, status,
                created_by, created_at
            ) VALUES (
                :id, :reconciliation_id, :snapshot_id,
                :customer_id, :customer_name,
                :sales_record_id, :payment_record_id,
                :sales_document_no, :payment_reference_no,
                :sales_date, :payment_date,
                :sales_amount, :payment_amount, :difference_amount,
                :match_rule, :match_score, 'PROPOSED',
                :created_by, :created_at
            )
        """), {
            "id": match_id,
            "reconciliation_id": reconciliation_id,
            "snapshot_id": case["snapshot_id"],
            "customer_id": case["customer_id"],
            "customer_name": case.get("customer_name", ""),
            "sales_record_id": sales_id,
            "payment_record_id": payment_id,
            "sales_document_no": str(
                sales_record.get("document_no")
                or sales_record.get("id")
                or ""
            ),
            "payment_reference_no": str(
                payment_record.get("reference_no")
                or payment_record.get("id")
                or ""
            ),
            "sales_date": str(sales_record.get("business_date") or ""),
            "payment_date": str(payment_record.get("business_date") or ""),
            "sales_amount": _fmt(sales_amount),
            "payment_amount": _fmt(_decimal(payment_record.get("amount"))),
            "difference_amount": _fmt(difference),
            "match_rule": rule,
            "match_score": score,
            "created_by": operator,
            "created_at": now,
        })
        _audit(
            db,
            auto_match_id=match_id,
            reconciliation_id=reconciliation_id,
            event_type="AUTO_MATCH_PROPOSED",
            actor=operator,
            new_status="PROPOSED",
            message=rule,
        )
        db.commit()

        row = db.execute(
            text(f"SELECT * FROM {MATCH_TABLE} WHERE id=:id"),
            {"id": match_id},
        ).first()
        proposals.append(_row(row))
        used_payments.add(payment_id)
        created += 1

    return {
        "reconciliation_id": reconciliation_id,
        "sales_record_count": sales["record_count"],
        "payment_record_count": payments["record_count"],
        "created_count": created,
        "existing_count": existing,
        "proposal_count": len(proposals),
        "proposals": proposals,
    }


def update_match_status(
    db: Session,
    *,
    auto_match_id: str,
    status: str,
    operator: str,
    note: str = "",
) -> dict[str, Any]:
    ensure_tables(db)

    current = db.execute(
        text(f"SELECT * FROM {MATCH_TABLE} WHERE id=:id"),
        {"id": auto_match_id},
    ).first()
    if not current:
        raise LookupError("Auto match not found")

    record = _row(current)
    status = str(status or "").strip().upper()
    operator = str(operator or "").strip()

    if status not in {"MATCHED", "REJECTED", "CANCELLED"}:
        raise ValueError("status must be MATCHED, REJECTED or CANCELLED")
    if not operator:
        raise ValueError("operator is required")
    if record["status"] not in {"PROPOSED", "MATCHED"}:
        raise ValueError("Only PROPOSED or MATCHED item can be updated")

    now = datetime.now(timezone.utc).isoformat()
    confirmed_by = operator if status == "MATCHED" else ""
    confirmed_at = now if status == "MATCHED" else ""

    db.execute(text(f"""
        UPDATE {MATCH_TABLE}
        SET status=:status,
            confirmed_by=:confirmed_by,
            confirmed_at=:confirmed_at,
            note=:note
        WHERE id=:id
    """), {
        "id": auto_match_id,
        "status": status,
        "confirmed_by": confirmed_by,
        "confirmed_at": confirmed_at,
        "note": str(note or ""),
    })
    _audit(
        db,
        auto_match_id=auto_match_id,
        reconciliation_id=record["reconciliation_id"],
        event_type="AUTO_MATCH_STATUS_CHANGED",
        actor=operator,
        old_status=record["status"],
        new_status=status,
        message=note,
    )
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {MATCH_TABLE} WHERE id=:id"),
        {"id": auto_match_id},
    ).first()
    return _row(row)


def list_auto_matches(
    db: Session,
    *,
    reconciliation_id: str = "",
    status: str = "",
    limit: int = 1000,
) -> list[dict[str, Any]]:
    ensure_tables(db)

    clauses = []
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 2000)}

    if reconciliation_id:
        clauses.append("reconciliation_id=:reconciliation_id")
        params["reconciliation_id"] = reconciliation_id

    if status:
        status = status.strip().upper()
        if status not in ALLOWED_STATUSES:
            raise ValueError("Unsupported auto match status")
        clauses.append("status=:status")
        params["status"] = status

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(text(f"""
        SELECT * FROM {MATCH_TABLE}
        {where}
        ORDER BY created_at DESC
        LIMIT :limit
    """), params).all()
    return [_row(row) for row in rows]


def list_auto_match_audit(
    db: Session,
    *,
    auto_match_id: str,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    ensure_tables(db)
    rows = db.execute(text(f"""
        SELECT * FROM {AUDIT_TABLE}
        WHERE auto_match_id=:auto_match_id
        ORDER BY event_at DESC
        LIMIT :limit
    """), {
        "auto_match_id": auto_match_id,
        "limit": min(max(int(limit), 1), 2000),
    }).all()
    return [_row(row) for row in rows]

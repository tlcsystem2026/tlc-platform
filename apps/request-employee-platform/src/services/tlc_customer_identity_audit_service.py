from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_customer_name_identity_service import AUDIT_TABLE, TABLE, ensure_schema
from src.services.tlc_customer_master_service import ensure_customer_master_table


MARKER = "TLC_CUSTOMER_IDENTITY_AUDIT_CONFLICT_CENTER_R1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prepare(db: Session) -> None:
    ensure_customer_master_table(db)
    exists = db.execute(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"), {"name": TABLE}).first()
    if not exists:
        ensure_schema(db)


def scan_conflicts(db: Session) -> dict[str, Any]:
    _prepare(db)
    issues: list[dict[str, Any]] = []
    rows = db.execute(text(f"""SELECT i.*,c.formal_name,c.active AS customer_active,c.customer_id AS master_customer_id
      FROM {TABLE} i LEFT JOIN tlc_customer_master c ON c.id=i.customer_record_id
      WHERE i.active=1 ORDER BY i.customer_id,i.name_value""")).all()
    for raw in rows:
        row = dict(raw._mapping)
        issue_type = ""
        if row.get("formal_name") is None:
            issue_type = "ORPHAN_IDENTITY"
        elif str(row.get("customer_id") or "") != str(row.get("master_customer_id") or ""):
            issue_type = "CUSTOMER_ID_MISMATCH"
        elif not bool(row.get("customer_active")):
            issue_type = "INACTIVE_CUSTOMER"
        if issue_type:
            issues.append({"issue_type": issue_type, "severity": "CRITICAL", **row})

    duplicates = db.execute(text(f"""SELECT normalized_name,COUNT(*) AS row_count
      FROM {TABLE} WHERE active=1 GROUP BY normalized_name HAVING COUNT(*)>1""")).all()
    for duplicate in duplicates:
        normalized = duplicate._mapping["normalized_name"]
        for raw in db.execute(text(f"SELECT * FROM {TABLE} WHERE active=1 AND normalized_name=:name"), {"name": normalized}).all():
            issues.append({"issue_type": "DUPLICATE_ACTIVE_NAME", "severity": "CRITICAL", **dict(raw._mapping)})

    missing = db.execute(text(f"""SELECT c.id,c.customer_id,c.formal_name FROM tlc_customer_master c
      WHERE c.active=1 AND NOT EXISTS(SELECT 1 FROM {TABLE} i
        WHERE i.customer_record_id=c.id AND i.active=1 AND i.name_type='FORMAL')
      ORDER BY c.customer_id""")).all()
    for raw in missing:
        issues.append({"issue_type": "MISSING_FORMAL_IDENTITY", "severity": "WARNING", **dict(raw._mapping)})

    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue["issue_type"]] = counts.get(issue["issue_type"], 0) + 1
    blocking = sum(value for key, value in counts.items() if key != "MISSING_FORMAL_IDENTITY")
    return {"marker": MARKER, "total": len(issues), "blocking": blocking,
            "ready_for_column_removal": blocking == 0 and not counts.get("MISSING_FORMAL_IDENTITY"),
            "counts": counts, "items": issues}


def impact_preview(db: Session, identity_id: str) -> dict[str, Any]:
    _prepare(db)
    identity = db.execute(text(f"SELECT * FROM {TABLE} WHERE id=:id"), {"id": identity_id}).first()
    if not identity:
        raise LookupError("Customer name identity was not found")
    item = dict(identity._mapping)
    tables = (
        "request_pending_review", "formal_sales_ledger", "tlc_request_review_queue",
        "tlc_customer_candidate", "tlc_bank_remitter_candidate", "bank_transaction_import",
        "tlc_customer_reconciliation_case",
    )
    impacts: list[dict[str, Any]] = []
    for table_name in tables:
        if not db.execute(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"), {"name": table_name}).first():
            continue
        columns = {str(row[1]) for row in db.execute(text(f"PRAGMA table_info({table_name})")).all()}
        conditions, params = [], {}
        for column in ("customer_id", "matched_customer_id", "matched_customer_code"):
            if column in columns:
                conditions.append(f"{column}=:customer_id"); params["customer_id"] = item["customer_id"]
        for column in ("raw_customer_name", "raw_remitter_name", "customer_name", "counterparty"):
            if column in columns:
                conditions.append(f"{column}=:name_value"); params["name_value"] = item["name_value"]
        if conditions:
            count = int(db.execute(text(f"SELECT COUNT(*) FROM {table_name} WHERE " + " OR ".join(conditions)), params).scalar_one() or 0)
            if count:
                impacts.append({"table": table_name, "count": count})
    return {"identity": item, "impacts": impacts, "total": sum(row["count"] for row in impacts)}


def resolve_conflict(db: Session, identity_id: str, action: str, actor: str,
                     reason: str, target_customer_id: str = "") -> dict[str, Any]:
    _prepare(db)
    actor, reason, action = str(actor or "").strip(), str(reason or "").strip(), str(action or "").strip().upper()
    if not actor or not reason:
        raise ValueError("Actor and reason are required")
    row = db.execute(text(f"SELECT * FROM {TABLE} WHERE id=:id"), {"id": identity_id}).first()
    if not row:
        raise LookupError("Customer name identity was not found")
    item, stamp = dict(row._mapping), _now()
    detail: dict[str, Any] = {"reason": reason, "before": item}
    if action == "DEACTIVATE":
        if item["name_type"] == "FORMAL":
            raise ValueError("Formal identity must be corrected through customer master")
        db.execute(text(f"UPDATE {TABLE} SET active=0,updated_at=:stamp WHERE id=:id"), {"stamp": stamp, "id": identity_id})
    elif action in {"MOVE", "REPAIR_CUSTOMER_ID"}:
        target = str(target_customer_id or item["customer_record_id"]).strip()
        customer = db.execute(text("SELECT id,customer_id,formal_name FROM tlc_customer_master WHERE active=1 AND (id=:target OR customer_id=:target) LIMIT 1"), {"target": target}).first()
        if not customer:
            raise ValueError("Active target customer was not found")
        customer = dict(customer._mapping)
        if action == "MOVE" and item["name_type"] == "FORMAL":
            raise ValueError("Formal identity cannot be moved here")
        db.execute(text(f"UPDATE {TABLE} SET customer_record_id=:record,customer_id=:customer,updated_at=:stamp WHERE id=:id"),
                   {"record": customer["id"], "customer": customer["customer_id"], "stamp": stamp, "id": identity_id})
        detail["target"] = customer
    else:
        raise ValueError("Action must be DEACTIVATE, MOVE, or REPAIR_CUSTOMER_ID")
    db.execute(text(f"""INSERT INTO {AUDIT_TABLE}(id,identity_id,customer_id,action,actor,detail,created_at)
      VALUES(:id,:identity,:customer,:action,:actor,:detail,:stamp)"""), {
        "id": uuid4().hex, "identity": identity_id, "customer": item["customer_id"],
        "action": "RESOLVE_" + action, "actor": actor, "detail": json.dumps(detail, ensure_ascii=False), "stamp": stamp})
    db.commit()
    return {"id": identity_id, "action": action, "resolved": True}

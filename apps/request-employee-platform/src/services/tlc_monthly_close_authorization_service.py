
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_monthly_close_checklist_service import (
    SIGNOFF_TABLE,
    ensure_tables as ensure_close_tables,
)
from src.services.tlc_monthly_close_control_service import monthly_close_overview


AUTH_TABLE = "tlc_monthly_close_authorization"
AUDIT_TABLE = "tlc_monthly_close_audit"

ALLOWED_ACTIONS = {"CLOSE", "REOPEN"}
ALLOWED_DECISIONS = {"PENDING", "APPROVED", "REJECTED", "EXECUTED", "CANCELLED"}


def ensure_tables(db: Session) -> None:
    ensure_close_tables(db)
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {AUTH_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            business_month VARCHAR(32) NOT NULL,
            action VARCHAR(64) NOT NULL,
            decision VARCHAR(64) NOT NULL DEFAULT 'PENDING',
            requested_by VARCHAR(255) NOT NULL,
            requested_at VARCHAR(64) NOT NULL,
            request_reason TEXT NOT NULL DEFAULT '',
            approved_by VARCHAR(255) NOT NULL DEFAULT '',
            approved_at VARCHAR(64) NOT NULL DEFAULT '',
            approval_note TEXT NOT NULL DEFAULT '',
            executed_by VARCHAR(255) NOT NULL DEFAULT '',
            executed_at VARCHAR(64) NOT NULL DEFAULT '',
            UNIQUE(business_month, action, decision)
        )
    """))
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            business_month VARCHAR(32) NOT NULL,
            authorization_id VARCHAR(64) NOT NULL,
            action VARCHAR(64) NOT NULL,
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


def _audit(
    db: Session,
    *,
    business_month: str,
    authorization_id: str,
    action: str,
    event_type: str,
    actor: str,
    old_status: str = "",
    new_status: str = "",
    message: str = "",
) -> None:
    db.execute(text(f"""
        INSERT INTO {AUDIT_TABLE} (
            id, business_month, authorization_id, action,
            event_type, actor, event_at,
            old_status, new_status, message
        ) VALUES (
            :id, :business_month, :authorization_id, :action,
            :event_type, :actor, :event_at,
            :old_status, :new_status, :message
        )
    """), {
        "id": uuid4().hex,
        "business_month": business_month,
        "authorization_id": authorization_id,
        "action": action,
        "event_type": event_type,
        "actor": actor,
        "event_at": datetime.now(timezone.utc).isoformat(),
        "old_status": old_status,
        "new_status": new_status,
        "message": message,
    })


def request_authorization(
    db: Session,
    *,
    business_month: str,
    action: str,
    requested_by: str,
    reason: str = "",
) -> dict[str, Any]:
    ensure_tables(db)

    business_month = str(business_month or "").strip()
    action = str(action or "").strip().upper()
    requested_by = str(requested_by or "").strip()

    if not business_month:
        raise ValueError("business_month is required")
    if action not in ALLOWED_ACTIONS:
        raise ValueError("Unsupported authorization action")
    if not requested_by:
        raise ValueError("requested_by is required")

    existing = db.execute(text(f"""
        SELECT *
        FROM {AUTH_TABLE}
        WHERE business_month=:business_month
          AND action=:action
          AND decision='PENDING'
    """), {
        "business_month": business_month,
        "action": action,
    }).first()
    if existing:
        return {"status": "exists", "authorization": _row(existing)}

    now = datetime.now(timezone.utc).isoformat()
    auth_id = uuid4().hex
    db.execute(text(f"""
        INSERT INTO {AUTH_TABLE} (
            id, business_month, action, decision,
            requested_by, requested_at, request_reason,
            approved_by, approved_at, approval_note,
            executed_by, executed_at
        ) VALUES (
            :id, :business_month, :action, 'PENDING',
            :requested_by, :requested_at, :request_reason,
            '', '', '', '', ''
        )
    """), {
        "id": auth_id,
        "business_month": business_month,
        "action": action,
        "requested_by": requested_by,
        "requested_at": now,
        "request_reason": str(reason or ""),
    })
    _audit(
        db,
        business_month=business_month,
        authorization_id=auth_id,
        action=action,
        event_type="AUTHORIZATION_REQUESTED",
        actor=requested_by,
        new_status="PENDING",
        message=reason,
    )
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {AUTH_TABLE} WHERE id=:id"),
        {"id": auth_id},
    ).first()
    return {"status": "created", "authorization": _row(row)}


def decide_authorization(
    db: Session,
    *,
    authorization_id: str,
    decision: str,
    approver: str,
    note: str = "",
) -> dict[str, Any]:
    ensure_tables(db)

    current = db.execute(
        text(f"SELECT * FROM {AUTH_TABLE} WHERE id=:id"),
        {"id": authorization_id},
    ).first()
    if not current:
        raise LookupError("Authorization not found")

    record = _row(current)
    decision = str(decision or "").strip().upper()
    approver = str(approver or "").strip()

    if decision not in {"APPROVED", "REJECTED", "CANCELLED"}:
        raise ValueError("Decision must be APPROVED, REJECTED or CANCELLED")
    if not approver:
        raise ValueError("approver is required")
    if record["decision"] != "PENDING":
        raise ValueError("Only PENDING authorization can be decided")
    if approver == record["requested_by"]:
        raise ValueError("Requester and approver must be different")

    now = datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""
        UPDATE {AUTH_TABLE}
        SET decision=:decision,
            approved_by=:approved_by,
            approved_at=:approved_at,
            approval_note=:approval_note
        WHERE id=:id
    """), {
        "id": authorization_id,
        "decision": decision,
        "approved_by": approver,
        "approved_at": now,
        "approval_note": str(note or ""),
    })
    _audit(
        db,
        business_month=record["business_month"],
        authorization_id=authorization_id,
        action=record["action"],
        event_type="AUTHORIZATION_DECIDED",
        actor=approver,
        old_status="PENDING",
        new_status=decision,
        message=note,
    )
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {AUTH_TABLE} WHERE id=:id"),
        {"id": authorization_id},
    ).first()
    return _row(row)


def execute_authorization(
    db: Session,
    *,
    authorization_id: str,
    operator: str,
    note: str = "",
) -> dict[str, Any]:
    ensure_tables(db)

    current = db.execute(
        text(f"SELECT * FROM {AUTH_TABLE} WHERE id=:id"),
        {"id": authorization_id},
    ).first()
    if not current:
        raise LookupError("Authorization not found")

    record = _row(current)
    operator = str(operator or "").strip()
    if not operator:
        raise ValueError("operator is required")
    if record["decision"] != "APPROVED":
        raise ValueError("Authorization must be APPROVED before execution")

    signoff = db.execute(text(f"""
        SELECT *
        FROM {SIGNOFF_TABLE}
        WHERE business_month=:business_month
    """), {"business_month": record["business_month"]}).first()
    if not signoff:
        raise ValueError("Monthly close signoff not found")

    signoff_row = _row(signoff)

    if record["action"] == "CLOSE":
        overview = monthly_close_overview(db, record["business_month"])
        if not overview["close_ready"]:
            raise ValueError("Monthly close is not ready")
        if signoff_row["status"] != "APPROVED":
            raise ValueError("Monthly close signoff must be APPROVED")
        new_signoff_status = "APPROVED"
    else:
        if signoff_row["status"] != "APPROVED":
            raise ValueError("Only APPROVED month can be reopened")
        new_signoff_status = "REOPENED"
        db.execute(text(f"""
            UPDATE {SIGNOFF_TABLE}
            SET status='REOPENED',
                updated_by=:operator,
                updated_at=:updated_at,
                note=:note
            WHERE business_month=:business_month
        """), {
            "business_month": record["business_month"],
            "operator": operator,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "note": str(note or signoff_row["note"] or ""),
        })

    now = datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""
        UPDATE {AUTH_TABLE}
        SET decision='EXECUTED',
            executed_by=:executed_by,
            executed_at=:executed_at
        WHERE id=:id
    """), {
        "id": authorization_id,
        "executed_by": operator,
        "executed_at": now,
    })

    _audit(
        db,
        business_month=record["business_month"],
        authorization_id=authorization_id,
        action=record["action"],
        event_type="AUTHORIZATION_EXECUTED",
        actor=operator,
        old_status="APPROVED",
        new_status="EXECUTED",
        message=note or f"{record['action']} executed; signoff={new_signoff_status}",
    )
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {AUTH_TABLE} WHERE id=:id"),
        {"id": authorization_id},
    ).first()
    return _row(row)


def list_authorizations(
    db: Session,
    *,
    business_month: str = "",
    action: str = "",
    decision: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    ensure_tables(db)

    clauses = []
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 1000)}

    if business_month:
        clauses.append("business_month=:business_month")
        params["business_month"] = business_month

    if action:
        action = action.strip().upper()
        if action not in ALLOWED_ACTIONS:
            raise ValueError("Unsupported authorization action")
        clauses.append("action=:action")
        params["action"] = action

    if decision:
        decision = decision.strip().upper()
        if decision not in ALLOWED_DECISIONS:
            raise ValueError("Unsupported authorization decision")
        clauses.append("decision=:decision")
        params["decision"] = decision

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(text(f"""
        SELECT *
        FROM {AUTH_TABLE}
        {where}
        ORDER BY requested_at DESC
        LIMIT :limit
    """), params).all()
    return [_row(row) for row in rows]


def list_audit(
    db: Session,
    *,
    business_month: str = "",
    authorization_id: str = "",
    limit: int = 1000,
) -> list[dict[str, Any]]:
    ensure_tables(db)

    clauses = []
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 2000)}

    if business_month:
        clauses.append("business_month=:business_month")
        params["business_month"] = business_month

    if authorization_id:
        clauses.append("authorization_id=:authorization_id")
        params["authorization_id"] = authorization_id

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(text(f"""
        SELECT *
        FROM {AUDIT_TABLE}
        {where}
        ORDER BY event_at DESC
        LIMIT :limit
    """), params).all()
    return [_row(row) for row in rows]


def control_view(db: Session, business_month: str) -> dict[str, Any]:
    return {
        "business_month": business_month,
        "authorizations": list_authorizations(
            db,
            business_month=business_month,
            limit=1000,
        ),
        "audit": list_audit(
            db,
            business_month=business_month,
            limit=1000,
        ),
    }

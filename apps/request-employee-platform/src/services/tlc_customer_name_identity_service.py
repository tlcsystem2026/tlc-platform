from __future__ import annotations

import unicodedata
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

TABLE = "tlc_customer_name_identity"
AUDIT_TABLE = "tlc_customer_name_identity_audit"
NAME_TYPES = {"FORMAL", "REQUEST_NAME", "BANK_REMITTER", "HISTORICAL", "SHORT_NAME", "DELIVERY_NAME"}
LANGUAGE_CODES = {"zh", "ja", "und"}
MASTER_NAME_FIELDS = {
    "formal_name": "FORMAL",
    "short_name": "SHORT_NAME",
    "delivery_name_1": "DELIVERY_NAME",
    "delivery_name_2": "DELIVERY_NAME",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_identity_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    value = re.sub(r"[\s\u3000・･,，.。\-‐‑–—_()（）\[\]【】]+", "", value)
    return value


def resolve_language_code(name_value: str, language_code: str = "") -> str:
    """Resolve language conservatively; Han-only names may be Chinese or Japanese."""
    requested = str(language_code or "").strip().lower()
    if requested and requested != "auto":
        if requested not in LANGUAGE_CODES:
            raise ValueError("Unsupported language code; use zh, ja, und or auto")
        return requested
    value = str(name_value or "")
    if re.search(r"[\u3040-\u30ff\u31f0-\u31ff]", value):
        return "ja"
    return "und"


def ensure_schema(db: Session) -> None:
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {TABLE}(
      id VARCHAR(64) PRIMARY KEY,customer_record_id VARCHAR(64) NOT NULL,
      customer_id VARCHAR(128) NOT NULL,name_value VARCHAR(500) NOT NULL,
      normalized_name VARCHAR(1000) NOT NULL,name_type VARCHAR(32) NOT NULL,
      language_code VARCHAR(16) NOT NULL DEFAULT '',source_system VARCHAR(64) NOT NULL DEFAULT '',
      active INTEGER NOT NULL DEFAULT 1,created_by VARCHAR(255) NOT NULL DEFAULT '',
      created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL)"""))
    db.execute(text(f"""CREATE UNIQUE INDEX IF NOT EXISTS ux_{TABLE}_active_name
      ON {TABLE}(normalized_name) WHERE active=1"""))
    db.execute(text(f"""CREATE INDEX IF NOT EXISTS ix_{TABLE}_customer
      ON {TABLE}(customer_record_id,active)"""))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {AUDIT_TABLE}(
      id VARCHAR(64) PRIMARY KEY,identity_id VARCHAR(64) NOT NULL DEFAULT '',
      customer_id VARCHAR(128) NOT NULL DEFAULT '',action VARCHAR(64) NOT NULL,
      actor VARCHAR(255) NOT NULL DEFAULT '',detail TEXT NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL)"""))
    db.commit()


def register_name(db: Session, *, customer_record_id: str, customer_id: str,
                  name_value: str, name_type: str, language_code: str = "",
                  source_system: str = "", actor: str = "") -> dict[str, Any]:
    ensure_schema(db)
    value = str(name_value or "").strip()
    normalized = normalize_identity_name(value)
    kind = str(name_type or "").strip().upper()
    if not normalized:
        raise ValueError("Customer name is required")
    if kind not in NAME_TYPES:
        raise ValueError("Unsupported customer name type")
    customer = db.execute(text("""SELECT id,customer_id,formal_name FROM tlc_customer_master
      WHERE active=1 AND (id=:record OR customer_id=:customer) ORDER BY CASE WHEN id=:record THEN 0 ELSE 1 END LIMIT 1"""),
      {"record": str(customer_record_id or "").strip(), "customer": str(customer_id or "").strip()}).first()
    if not customer:
        raise ValueError("Active customer was not found")
    canonical = dict(customer._mapping)
    if customer_record_id and customer_id and (canonical["id"] != customer_record_id or canonical["customer_id"] != customer_id):
        raise ValueError("Customer internal ID and customer number do not identify the same customer")
    customer_record_id, customer_id = canonical["id"], canonical["customer_id"]
    existing = db.execute(text(f"SELECT * FROM {TABLE} WHERE normalized_name=:name AND active=1"),
                          {"name": normalized}).first()
    if existing:
        row = dict(existing._mapping)
        if row["customer_record_id"] != customer_record_id:
            raise ValueError(f"Customer name is already assigned to customer {row['customer_id']}")
        return row
    stamp, identity_id = now(), uuid4().hex
    db.execute(text(f"""INSERT INTO {TABLE}(id,customer_record_id,customer_id,name_value,
      normalized_name,name_type,language_code,source_system,active,created_by,created_at,updated_at)
      VALUES(:id,:record,:customer,:value,:normalized,:kind,:language,:source,1,:actor,:stamp,:stamp)"""), {
        "id": identity_id, "record": customer_record_id, "customer": customer_id,
        "value": value, "normalized": normalized, "kind": kind,
        "language": resolve_language_code(value, language_code),
        "source": str(source_system or "").strip(), "actor": str(actor or "").strip(), "stamp": stamp,
    })
    db.execute(text(f"INSERT INTO {AUDIT_TABLE}(id,identity_id,customer_id,action,actor,detail,created_at) "
                    "VALUES(:id,:identity,:customer,'REGISTER_NAME',:actor,:detail,:stamp)"), {
        "id": uuid4().hex, "identity": identity_id, "customer": customer_id,
        "actor": str(actor or "").strip(), "detail": f"{kind}:{value}", "stamp": stamp,
    })
    db.commit()
    return dict(db.execute(text(f"SELECT * FROM {TABLE} WHERE id=:id"), {"id": identity_id}).one()._mapping)


def backfill_customer_names(db: Session, actor: str = "MIGRATION") -> dict[str, int]:
    ensure_schema(db)
    columns = {str(r[1]) for r in db.execute(text("PRAGMA table_info(tlc_customer_master)")).all()}
    field_types = {
        "formal_name": "FORMAL", "short_name": "SHORT_NAME",
        "delivery_name_1": "DELIVERY_NAME", "delivery_name_2": "DELIVERY_NAME",
    }
    selected = [field for field in field_types if field in columns]
    rows = db.execute(text("SELECT id,customer_id," + ",".join(selected) +
                           " FROM tlc_customer_master WHERE active=1")).all()
    created = conflicts = 0
    for raw in rows:
        customer = dict(raw._mapping)
        for field in selected:
            value = str(customer.get(field) or "").strip()
            if not value:
                continue
            try:
                before = db.execute(text(f"SELECT id FROM {TABLE} WHERE normalized_name=:n AND active=1"),
                                    {"n": normalize_identity_name(value)}).first()
                register_name(db, customer_record_id=customer["id"], customer_id=customer["customer_id"],
                              name_value=value, name_type=field_types[field], source_system="CUSTOMER_MASTER",
                              actor=actor)
                created += int(before is None)
            except ValueError:
                conflicts += 1
    return {"customers": len(rows), "created": created, "conflicts": conflicts}


def synchronize_customer(db: Session, customer: dict[str, Any], actor: str = "SYSTEM") -> None:
    """Synchronize customer-master names without touching manually reviewed names."""
    ensure_schema(db)
    record_id, customer_id = str(customer["id"]), str(customer["customer_id"])
    stamp = now()

    # Customer number changes must propagate to every name identity.
    db.execute(text(f"""UPDATE {TABLE} SET customer_id=:customer,updated_at=:stamp
      WHERE customer_record_id=:record AND customer_id<>:customer"""),
               {"customer": customer_id, "stamp": stamp, "record": record_id})

    if not bool(customer.get("active", True)):
        db.execute(text(f"""UPDATE {TABLE} SET active=0,updated_at=:stamp
          WHERE customer_record_id=:record AND active=1"""),
                   {"stamp": stamp, "record": record_id})
        db.commit()
        return

    desired: dict[tuple[str, str], str] = {}
    for field_name, name_type in MASTER_NAME_FIELDS.items():
        value = str(customer.get(field_name) or "").strip()
        normalized = normalize_identity_name(value)
        if normalized:
            desired[(name_type, normalized)] = value

    # Only automatically retire rows that came from customer master. Names
    # approved from requests or bank remitters remain under manual control.
    master_rows = db.execute(text(f"""SELECT id,name_type,normalized_name FROM {TABLE}
      WHERE customer_record_id=:record AND source_system='CUSTOMER_MASTER' AND active=1"""),
                             {"record": record_id}).all()
    for row in master_rows:
        item = row._mapping
        if (str(item["name_type"]), str(item["normalized_name"])) not in desired:
            db.execute(text(f"UPDATE {TABLE} SET active=0,updated_at=:stamp WHERE id=:id"),
                       {"stamp": stamp, "id": item["id"]})
    db.commit()

    for (name_type, _normalized), value in desired.items():
        register_name(db, customer_record_id=record_id, customer_id=customer_id,
                      name_value=value, name_type=name_type,
                      source_system="CUSTOMER_MASTER", actor=actor)


def match_name(db: Session, name_value: str) -> dict[str, Any]:
    ensure_schema(db)
    normalized = normalize_identity_name(name_value)
    rows = db.execute(text(f"""SELECT i.*,c.formal_name,c.active AS customer_active
      FROM {TABLE} i JOIN tlc_customer_master c ON c.id=i.customer_record_id
      WHERE i.normalized_name=:name AND i.active=1 AND c.active=1"""), {"name": normalized}).all()
    if len(rows) != 1:
        return {"match_status": "AMBIGUOUS" if rows else "UNMATCHED", "candidate_count": len(rows)}
    row = dict(rows[0]._mapping)
    return {"match_status": "MATCHED", "candidate_count": 1,
            "customer_record_id": row["customer_record_id"], "customer_id": row["customer_id"],
            "customer_name": row["formal_name"], "identity_id": row["id"],
            "name_type": row["name_type"], "matched_value": row["name_value"], "score": 100}


def list_names(db: Session, query: str = "", customer_id: str = "", name_type: str = "",
               language_code: str = "", include_inactive: bool = False) -> list[dict[str, Any]]:
    ensure_schema(db)
    clauses, params = [], {}
    if query:
        clauses.append("(i.name_value LIKE :query OR i.normalized_name LIKE :query OR i.customer_id LIKE :query OR c.formal_name LIKE :query)")
        params["query"] = f"%{query}%"
    if customer_id:
        clauses.append("i.customer_id LIKE :customer_id"); params["customer_id"] = f"%{customer_id}%"
    if name_type:
        clauses.append("i.name_type=:name_type"); params["name_type"] = name_type.upper()
    if language_code:
        clauses.append("i.language_code=:language"); params["language"] = language_code.lower()
    if not include_inactive:
        clauses.append("i.active=1")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = db.execute(text(f"""SELECT i.*,c.formal_name AS customer_formal_name
      FROM {TABLE} i LEFT JOIN tlc_customer_master c ON c.id=i.customer_record_id
      {where} ORDER BY i.customer_id,i.name_type,i.name_value"""), params).all()
    return [dict(row._mapping) for row in rows]


def deactivate_name(db: Session, identity_id: str, actor: str, reason: str) -> dict[str, Any]:
    ensure_schema(db)
    row = db.execute(text(f"SELECT * FROM {TABLE} WHERE id=:id"), {"id": identity_id}).first()
    if not row:
        raise LookupError("Customer name identity was not found")
    item = dict(row._mapping)
    if item["name_type"] == "FORMAL":
        raise ValueError("Formal customer name cannot be deactivated here")
    if not str(actor or "").strip() or not str(reason or "").strip():
        raise ValueError("Actor and reason are required")
    stamp = now()
    db.execute(text(f"UPDATE {TABLE} SET active=0,updated_at=:stamp WHERE id=:id"), {"stamp": stamp, "id": identity_id})
    db.execute(text(f"INSERT INTO {AUDIT_TABLE}(id,identity_id,customer_id,action,actor,detail,created_at) "
                    "VALUES(:id,:identity,:customer,'DEACTIVATE_NAME',:actor,:detail,:stamp)"), {
        "id": uuid4().hex, "identity": identity_id, "customer": item["customer_id"],
        "actor": actor.strip(), "detail": reason.strip(), "stamp": stamp,
    })
    db.commit()
    return {"id": identity_id, "active": False}

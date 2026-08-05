from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


TABLE = "legal_entities"
AUDIT_TABLE = "tlc_legal_entity_master_audit"


class LegalEntityDeleteConflict(RuntimeError):
    def __init__(self, message: str, references: list[dict[str, Any]]):
        super().__init__(message)
        self.references = references


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(db: Session) -> None:
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {TABLE}(
      id VARCHAR(50) PRIMARY KEY,name VARCHAR(200) NOT NULL,
      country VARCHAR(10) NOT NULL DEFAULT 'JP',language VARCHAR(10) NOT NULL DEFAULT 'zh',
      created_at DATETIME,active INTEGER NOT NULL DEFAULT 1,
      is_default INTEGER NOT NULL DEFAULT 0,updated_at VARCHAR(64) NOT NULL DEFAULT '')"""))
    columns = {row._mapping["name"] for row in db.execute(text(f"PRAGMA table_info({TABLE})")).all()}
    additions = {
        "active": "INTEGER NOT NULL DEFAULT 1",
        "is_default": "INTEGER NOT NULL DEFAULT 0",
        "updated_at": "VARCHAR(64) NOT NULL DEFAULT ''",
    }
    for name, definition in additions.items():
        if name not in columns:
            db.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {name} {definition}"))
    db.execute(text(f"""CREATE TABLE IF NOT EXISTS {AUDIT_TABLE}(
      id INTEGER PRIMARY KEY AUTOINCREMENT,legal_entity_id VARCHAR(50) NOT NULL,
      action VARCHAR(32) NOT NULL,operator VARCHAR(255) NOT NULL DEFAULT '',
      detail TEXT NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL)"""))
    default_count = int(db.execute(text(f"SELECT COUNT(*) FROM {TABLE} WHERE is_default=1")).scalar_one() or 0)
    if default_count == 0:
        preferred = os.getenv("TLC_LEGAL_ENTITY_DEFAULT", "TEST-JP-01")
        row = db.execute(text(f"SELECT id FROM {TABLE} WHERE id=:id"), {"id": preferred}).first()
        if row is None:
            row = db.execute(text(f"SELECT id FROM {TABLE} ORDER BY id LIMIT 1")).first()
        if row is not None:
            db.execute(text(f"UPDATE {TABLE} SET is_default=1 WHERE id=:id"), {"id": row._mapping["id"]})
    db.commit()


def list_entities(db: Session, keyword: str = "", include_inactive: bool = True) -> list[dict[str, Any]]:
    ensure_schema(db)
    clauses, params = [], {}
    if keyword:
        clauses.append("(id LIKE :keyword OR name LIKE :keyword OR country LIKE :keyword OR language LIKE :keyword)")
        params["keyword"] = f"%{keyword}%"
    if not include_inactive:
        clauses.append("active=1")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = db.execute(text(f"SELECT * FROM {TABLE} {where} ORDER BY is_default DESC,id"), params).all()
    return [dict(row._mapping) for row in rows]


def _audit(db: Session, entity_id: str, action: str, operator: str, detail: str = "") -> None:
    db.execute(text(f"INSERT INTO {AUDIT_TABLE}(legal_entity_id,action,operator,detail,created_at) VALUES(:entity,:action,:operator,:detail,:created)"),
               {"entity": entity_id, "action": action, "operator": operator, "detail": detail, "created": _now()})


def save_entity(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_schema(db)
    entity_id = str(payload.get("id") or "").strip()
    name = str(payload.get("name") or "").strip()
    if not entity_id or not name:
        raise ValueError("法人代码和法人名称为必填项目")
    if len(entity_id) > 50:
        raise ValueError("法人代码不能超过50个字符")
    country = str(payload.get("country") or "JP").strip().upper()
    language = str(payload.get("language") or "zh").strip().lower()
    active = 1 if payload.get("active", True) else 0
    operator = str(payload.get("operator") or "").strip()
    existing = db.execute(text(f"SELECT id FROM {TABLE} WHERE id=:id"), {"id": entity_id}).first()
    now = _now()
    if existing:
        db.execute(text(f"UPDATE {TABLE} SET name=:name,country=:country,language=:language,active=:active,updated_at=:updated WHERE id=:id"),
                   {"id": entity_id, "name": name, "country": country, "language": language, "active": active, "updated": now})
        action = "UPDATE"
    else:
        db.execute(text(f"INSERT INTO {TABLE}(id,name,country,language,created_at,active,is_default,updated_at) VALUES(:id,:name,:country,:language,:created,:active,0,:updated)"),
                   {"id": entity_id, "name": name, "country": country, "language": language, "created": now, "active": active, "updated": now})
        action = "CREATE"
    _audit(db, entity_id, action, operator)
    db.commit()
    return next(row for row in list_entities(db) if row["id"] == entity_id)


def set_default(db: Session, entity_id: str, operator: str = "") -> dict[str, Any]:
    ensure_schema(db)
    row = db.execute(text(f"SELECT id,active FROM {TABLE} WHERE id=:id"), {"id": entity_id}).first()
    if row is None:
        raise LookupError("法人不存在")
    if not int(row._mapping["active"] or 0):
        raise ValueError("停用法人不能设为默认法人")
    db.execute(text(f"UPDATE {TABLE} SET is_default=0"))
    db.execute(text(f"UPDATE {TABLE} SET is_default=1,updated_at=:updated WHERE id=:id"), {"id": entity_id, "updated": _now()})
    _audit(db, entity_id, "SET_DEFAULT", operator)
    db.commit()
    return {"id": entity_id, "is_default": True}


def reference_counts(db: Session, entity_id: str) -> list[dict[str, Any]]:
    ensure_schema(db)
    references: list[dict[str, Any]] = []
    tables = [row._mapping["name"] for row in db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")).all()]
    excluded = {TABLE, AUDIT_TABLE}
    for table_name in tables:
        if table_name in excluded or not table_name.replace("_", "").isalnum():
            continue
        columns = {row._mapping["name"] for row in db.execute(text(f"PRAGMA table_info({table_name})")).all()}
        for column in ("legal_entity_id", "entity_id"):
            if column not in columns:
                continue
            count = int(db.execute(text(f"SELECT COUNT(*) FROM {table_name} WHERE {column}=:id"), {"id": entity_id}).scalar_one() or 0)
            if count:
                references.append({"table": table_name, "column": column, "count": count})
    return sorted(references, key=lambda item: (-item["count"], item["table"], item["column"]))


def _require_super_admin(operator: str, role: str) -> str:
    operator = str(operator or "").strip()
    if str(role or "").strip().upper() != "SUPER_ADMIN":
        raise PermissionError("SUPER_ADMIN role is required")
    allowed = {item.strip() for item in os.getenv("TLC_SUPER_ADMIN_OPERATORS", "super-admin").split(",") if item.strip()}
    if operator not in allowed:
        raise PermissionError("Operator is not configured as a SUPER_ADMIN")
    return operator


def delete_entity(db: Session, entity_id: str, operator: str, role: str) -> dict[str, Any]:
    ensure_schema(db)
    operator = _require_super_admin(operator, role)
    row = db.execute(text(f"SELECT id,name,is_default FROM {TABLE} WHERE id=:id"), {"id": entity_id}).first()
    if row is None:
        raise LookupError("法人不存在")
    if int(row._mapping["is_default"] or 0):
        raise ValueError("默认法人不能删除，请先指定其他默认法人")
    references = reference_counts(db, entity_id)
    if references:
        raise LegalEntityDeleteConflict("法人存在关联业务数据，不能删除", references)
    _audit(db, entity_id, "DELETE", operator, str(row._mapping["name"]))
    db.execute(text(f"DELETE FROM {TABLE} WHERE id=:id"), {"id": entity_id})
    db.commit()
    return {"deleted": True, "id": entity_id}


def audit_rows(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    ensure_schema(db)
    rows = db.execute(text(f"SELECT * FROM {AUDIT_TABLE} ORDER BY id DESC LIMIT :limit"), {"limit": min(max(int(limit), 1), 1000)}).all()
    return [dict(row._mapping) for row in rows]

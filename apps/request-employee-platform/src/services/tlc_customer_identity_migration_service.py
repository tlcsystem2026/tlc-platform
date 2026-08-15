from __future__ import annotations

from typing import Any
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from src.services.tlc_customer_name_identity_service import backfill_customer_names

PRESERVE_EXACT = {
    "tlc_customer_master", "tlc_customer_name_identity", "tlc_customer_name_identity_audit",
    "legal_entities", "alembic_version", "sqlite_sequence",
}
PRESERVE_TOKENS = (
    "user", "role", "permission", "access", "security", "session", "mfa", "audit",
    "code", "parameter", "setting", "legal_entity", "department", "bank_account", "bank_master",
)


def migration_plan(db: Session) -> dict[str, Any]:
    tables = sorted(inspect(db.bind).get_table_names())
    preserved, cleared = [], []
    for table in tables:
        lower = table.lower()
        if table in PRESERVE_EXACT or any(token in lower for token in PRESERVE_TOKENS):
            preserved.append(table)
        else:
            cleared.append(table)
    return {"preserved_tables": preserved, "clear_tables": cleared}


def migrate_customer_only(db: Session, confirmation: str, actor: str) -> dict[str, Any]:
    if confirmation != "MIGRATE_CUSTOMER_ONLY_AND_CLEAR_BUSINESS_DATA":
        raise ValueError("Exact migration confirmation is required")
    if not str(actor or "").strip():
        raise ValueError("Migration actor is required")
    identity = backfill_customer_names(db, actor=actor)
    plan = migration_plan(db)
    deleted: dict[str, int] = {}
    try:
        db.execute(text("PRAGMA foreign_keys=OFF"))
        for table in plan["clear_tables"]:
            quoted = '"' + table.replace('"', '""') + '"'
            count = int(db.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar_one() or 0)
            db.execute(text(f"DELETE FROM {quoted}"))
            deleted[table] = count
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.execute(text("PRAGMA foreign_keys=ON"))
    return {"identity_migration": identity, "preserved_tables": plan["preserved_tables"],
            "cleared_tables": deleted}

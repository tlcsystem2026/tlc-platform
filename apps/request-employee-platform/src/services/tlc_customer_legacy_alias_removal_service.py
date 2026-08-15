from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_customer_identity_audit_service import scan_conflicts
from src.services.tlc_customer_name_identity_service import backfill_customer_names, migrate_legacy_aliases

LEGACY_ALIAS_COLUMNS = ("alias_1", "alias_2", "alias_3", "alias_4", "alias_5")
CONTRACT = "TLC_CUSTOMER_LEGACY_ALIAS_COLUMNS_REMOVAL_R1"


def customer_columns(db: Session) -> set[str]:
    return {str(row[1]) for row in db.execute(text("PRAGMA table_info(tlc_customer_master)")).all()}


def remove_legacy_alias_columns(db: Session, actor: str = "LEGACY_ALIAS_COLUMN_REMOVAL") -> dict[str, Any]:
    """Migrate aliases, enforce the conflict gate, then remove only Alias1..Alias5."""
    before = customer_columns(db)
    pending = [column for column in LEGACY_ALIAS_COLUMNS if column in before]
    if not pending:
        return {"removed": [], "already_removed": True, "ready_for_column_removal": True}

    migration = migrate_legacy_aliases(db, actor=actor)
    if int(migration.get("conflict_count", 0)):
        raise RuntimeError("Legacy alias migration has conflicts; no column was removed")

    backfill = backfill_customer_names(db, actor=actor)
    if int(backfill.get("conflicts", 0)):
        raise RuntimeError("Customer name backfill has conflicts; no column was removed")

    audit = scan_conflicts(db)
    if not audit.get("ready_for_column_removal"):
        raise RuntimeError("Customer identity audit is not ready; no column was removed")

    try:
        for column in pending:
            db.execute(text(f'ALTER TABLE tlc_customer_master DROP COLUMN "{column}"'))
        db.commit()
    except Exception:
        db.rollback()
        raise

    remaining = customer_columns(db)
    if any(column in remaining for column in LEGACY_ALIAS_COLUMNS):
        raise RuntimeError("Legacy alias column removal verification failed")
    return {
        "removed": pending,
        "already_removed": False,
        "ready_for_column_removal": True,
        "migration": migration,
        "backfill": backfill,
        "audit_total": int(audit.get("total", 0)),
    }

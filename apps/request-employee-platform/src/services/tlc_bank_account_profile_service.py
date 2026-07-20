from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_code_master_service import ensure_tlc_code_tables


TABLE_NAME = "tlc_bank_account_profile"


def ensure_table(db: Session) -> None:
    ensure_tlc_code_tables(db)
    db.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME}(
                id VARCHAR(64) PRIMARY KEY,
                bank_code VARCHAR(128) NOT NULL,
                branch_code VARCHAR(128) NOT NULL DEFAULT '',
                branch_name VARCHAR(255) NOT NULL DEFAULT '',
                account_type VARCHAR(128) NOT NULL DEFAULT '',
                account_number VARCHAR(255) NOT NULL,
                account_holder VARCHAR(500) NOT NULL DEFAULT '',
                adapter_code VARCHAR(128) NOT NULL DEFAULT '',
                file_encoding VARCHAR(64) NOT NULL DEFAULT 'cp932',
                active INTEGER NOT NULL DEFAULT 1,
                note TEXT NOT NULL DEFAULT '',
                created_at VARCHAR(64) NOT NULL,
                updated_at VARCHAR(64) NOT NULL,
                UNIQUE(bank_code, account_number)
            )
            """
        )
    )
    db.commit()


def seed_banks(db: Session) -> None:
    ensure_tlc_code_tables(db)
    now = datetime.now(timezone.utc).isoformat()
    defaults = [
        (
            "SUGAMO_SHINKIN",
            "巣鴨信用金庫",
            "巣鴨信用金庫",
            "Sugamo Shinkin Bank",
            10,
        ),
        (
            "JAPAN_POST_BANK",
            "邮储银行",
            "ゆうちょう銀行",
            "Japan Post Bank",
            20,
        ),
    ]
    for code, zh, ja, en, sort in defaults:
        exists = db.execute(
            text(
                """
                SELECT id
                FROM tlc_code_value
                WHERE category_code='BANK' AND code=:code
                """
            ),
            {"code": code},
        ).first()
        if exists:
            continue
        db.execute(
            text(
                """
                INSERT INTO tlc_code_value(
                    id, category_code, code, name_zh, name_ja, name_en,
                    sort_order, active, extra_json, created_at, updated_at
                )
                VALUES(
                    :id, 'BANK', :code, :zh, :ja, :en,
                    :sort, 1, '{}', :now, :now
                )
                """
            ),
            {
                "id": uuid4().hex,
                "code": code,
                "zh": zh,
                "ja": ja,
                "en": en,
                "sort": sort,
                "now": now,
            },
        )
    db.commit()


def _row(value: Any) -> dict[str, Any]:
    data = dict(value._mapping)
    data["active"] = bool(data["active"])
    return data


def list_profiles(
    db: Session,
    bank_code: str = "",
    account_number: str = "",
) -> list[dict[str, Any]]:
    ensure_table(db)
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if bank_code:
        clauses.append("bank_code=:bank")
        params["bank"] = bank_code
    if account_number:
        clauses.append("account_number LIKE :account")
        params["account"] = f"%{account_number}%"
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = db.execute(
        text(
            f"""
            SELECT *
            FROM {TABLE_NAME}
            {where}
            ORDER BY bank_code, branch_code, account_number
            """
        ),
        params,
    ).all()
    return [_row(row) for row in rows]


def _read_profile_no_ensure(
    db: Session,
    record_id: str,
) -> dict[str, Any]:
    row = db.execute(
        text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),
        {"id": record_id},
    ).first()
    if not row:
        raise LookupError("Bank account profile not found")
    return _row(row)


def _as_active(value: Any) -> int:
    if isinstance(value, str):
        return 0 if value.strip().lower() in {"0", "false", "no", "off"} else 1
    return 1 if value else 0


def _save_profile(
    db: Session,
    payload: dict[str, Any],
    *,
    commit: bool,
) -> dict[str, Any]:
    bank = str(payload.get("bank_code", "")).strip().upper()
    account = str(payload.get("account_number", "")).strip()
    record_id = str(payload.get("id", "")).strip()

    if not bank or not account:
        raise ValueError("bank_code and account_number are required")

    bank_exists = db.execute(
        text(
            """
            SELECT id
            FROM tlc_code_value
            WHERE category_code='BANK' AND code=:code
            """
        ),
        {"code": bank},
    ).first()
    if not bank_exists:
        raise ValueError("bank_code does not exist in TLC Code Master")

    duplicate = db.execute(
        text(
            f"""
            SELECT id
            FROM {TABLE_NAME}
            WHERE bank_code=:bank AND account_number=:account
            """
        ),
        {"bank": bank, "account": account},
    ).first()

    now = datetime.now(timezone.utc).isoformat()
    values = {
        "bank_code": bank,
        "branch_code": str(payload.get("branch_code", "")).strip(),
        "branch_name": str(payload.get("branch_name", "")).strip(),
        "account_type": str(payload.get("account_type", "")).strip(),
        "account_number": account,
        "account_holder": str(payload.get("account_holder", "")).strip(),
        "adapter_code": str(payload.get("adapter_code", "")).strip(),
        "file_encoding": str(
            payload.get("file_encoding", "cp932") or "cp932"
        ).strip(),
        "active": _as_active(payload.get("active", True)),
        "note": str(payload.get("note", "")).strip(),
        "updated_at": now,
    }

    if record_id:
        if duplicate and duplicate._mapping["id"] != record_id:
            raise ValueError("bank account already exists")
        values["id"] = record_id
        result = db.execute(
            text(
                f"""
                UPDATE {TABLE_NAME}
                SET bank_code=:bank_code,
                    branch_code=:branch_code,
                    branch_name=:branch_name,
                    account_type=:account_type,
                    account_number=:account_number,
                    account_holder=:account_holder,
                    adapter_code=:adapter_code,
                    file_encoding=:file_encoding,
                    active=:active,
                    note=:note,
                    updated_at=:updated_at
                WHERE id=:id
                """
            ),
            values,
        )
        if result.rowcount == 0:
            raise LookupError("Bank account profile not found")
    else:
        if duplicate:
            raise ValueError("bank account already exists")
        record_id = uuid4().hex
        values.update({"id": record_id, "created_at": now})
        db.execute(
            text(
                f"""
                INSERT INTO {TABLE_NAME}(
                    id, bank_code, branch_code, branch_name, account_type,
                    account_number, account_holder, adapter_code,
                    file_encoding, active, note, created_at, updated_at
                )
                VALUES(
                    :id, :bank_code, :branch_code, :branch_name, :account_type,
                    :account_number, :account_holder, :adapter_code,
                    :file_encoding, :active, :note, :created_at, :updated_at
                )
                """
            ),
            values,
        )

    if commit:
        db.commit()
    return _read_profile_no_ensure(db, record_id)


def save_profile(
    db: Session,
    payload: dict[str, Any],
) -> dict[str, Any]:
    ensure_table(db)
    seed_banks(db)
    return _save_profile(db, payload, commit=True)


def import_profiles(
    db: Session,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_table(db)
    seed_banks(db)
    if not rows:
        raise ValueError("rows is empty")

    imported: list[dict[str, Any]] = []
    try:
        for index, row in enumerate(rows, start=2):
            if not isinstance(row, dict):
                raise ValueError(f"CSV row {index} is not an object")
            try:
                imported.append(_save_profile(db, row, commit=False))
            except (ValueError, LookupError) as exc:
                raise ValueError(f"CSV row {index}: {exc}") from exc
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "imported_count": len(imported),
        "rows": imported,
    }



class BankDeleteConflict(ValueError):
    def __init__(self, message: str, references: list[dict[str, Any]]):
        super().__init__(message)
        self.references = references


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _sqlite_tables(db: Session) -> list[str]:
    return [
        str(row._mapping["name"])
        for row in db.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ).all()
    ]


def _table_columns(db: Session, table_name: str) -> set[str]:
    quoted = _quote_identifier(table_name)
    return {
        str(row._mapping["name"])
        for row in db.execute(text(f"PRAGMA table_info({quoted})")).all()
    }


def _reference_counts(
    db: Session,
    excluded_tables: set[str],
    candidate_values: dict[str, str],
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for table_name in _sqlite_tables(db):
        if table_name in excluded_tables:
            continue
        columns = _table_columns(db, table_name)
        for column_name, expected in candidate_values.items():
            if not expected or column_name not in columns:
                continue
            table_q = _quote_identifier(table_name)
            column_q = _quote_identifier(column_name)
            count = db.execute(
                text(
                    f"SELECT COUNT(*) FROM {table_q} "
                    f"WHERE {column_q}=:value"
                ),
                {"value": expected},
            ).scalar_one()
            if int(count or 0) > 0:
                references.append(
                    {
                        "table": table_name,
                        "column": column_name,
                        "count": int(count),
                    }
                )
    return references


def delete_profiles(
    db: Session,
    record_ids: list[str],
) -> dict[str, Any]:
    ensure_table(db)
    ids: list[str] = []
    for value in record_ids or []:
        clean = str(value or "").strip()
        if clean and clean not in ids:
            ids.append(clean)
    if not ids:
        raise ValueError("ids is required")

    targets: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for record_id in ids:
        row = db.execute(
            text(
                f"SELECT id,bank_code,account_number,account_holder "
                f"FROM {TABLE_NAME} WHERE id=:id"
            ),
            {"id": record_id},
        ).first()
        if not row:
            raise LookupError(f"Bank account profile not found: {record_id}")
        target = dict(row._mapping)
        references = _reference_counts(
            db,
            {TABLE_NAME},
            {
                "bank_account_id": target["id"],
                "bank_account_profile_id": target["id"],
                "account_profile_id": target["id"],
                "account_number": target["account_number"],
            },
        )
        if references:
            blocked.append({**target, "references": references})
        targets.append(target)

    if blocked:
        raise BankDeleteConflict(
            "Bank account has associated data. Delete or unlink the "
            "associated data before deleting the bank account.",
            blocked,
        )

    try:
        for target in targets:
            db.execute(
                text(f"DELETE FROM {TABLE_NAME} WHERE id=:id"),
                {"id": target["id"]},
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "deleted": len(targets),
        "ids": [target["id"] for target in targets],
    }


def delete_banks(
    db: Session,
    bank_value_ids: list[str],
) -> dict[str, Any]:
    ensure_table(db)
    ids: list[str] = []
    for value in bank_value_ids or []:
        clean = str(value or "").strip()
        if clean and clean not in ids:
            ids.append(clean)
    if not ids:
        raise ValueError("ids is required")

    targets: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for value_id in ids:
        row = db.execute(
            text(
                "SELECT id,code,name_zh,name_ja,name_en "
                "FROM tlc_code_value "
                "WHERE id=:id AND category_code='BANK'"
            ),
            {"id": value_id},
        ).first()
        if not row:
            raise LookupError(f"Bank Master not found: {value_id}")
        target = dict(row._mapping)

        account_count = db.execute(
            text(
                f"SELECT COUNT(*) FROM {TABLE_NAME} "
                "WHERE bank_code=:bank_code"
            ),
            {"bank_code": target["code"]},
        ).scalar_one()
        references: list[dict[str, Any]] = []
        if int(account_count or 0) > 0:
            references.append(
                {
                    "table": TABLE_NAME,
                    "column": "bank_code",
                    "count": int(account_count),
                }
            )

        references.extend(
            _reference_counts(
                db,
                {"tlc_code_value", TABLE_NAME},
                {
                    "bank_master_id": target["id"],
                    "bank_code": target["code"],
                },
            )
        )

        if references:
            blocked.append({**target, "references": references})
        targets.append(target)

    if blocked:
        raise BankDeleteConflict(
            "Bank Master has associated bank accounts or business data. "
            "Delete the associated data first.",
            blocked,
        )

    try:
        for target in targets:
            db.execute(
                text(
                    "DELETE FROM tlc_code_value "
                    "WHERE id=:id AND category_code='BANK'"
                ),
                {"id": target["id"]},
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "deleted": len(targets),
        "ids": [target["id"] for target in targets],
    }

from __future__ import annotations

import csv
import base64
import io
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_code_master_service import ensure_tlc_code_tables


TABLE_NAME = "tlc_customer_master"
EXPORT_FIELDS = [
    "customer_id",
    "formal_name",
    "hiragana_name",
    "katakana_name",
    "katakana_name_short",
    "delivery_name_1",
    "delivery_name_2",
    "short_name",
    "alias_1",
    "alias_2",
    "alias_3",
    "alias_4",
    "alias_5",
    "status_code",
    "active",
    "note",
]

TODOKEDL_FIELDS = {
    "お届け先コード": "customer_id",
    "カナ名称": "katakana_name_short",
    "お届け先名称１": "delivery_name_1",
    "お届け先名称２": "delivery_name_2",
}


def normalize_customer_name(value: str) -> str:
    text_value = unicodedata.normalize("NFKC", str(value or ""))
    text_value = text_value.casefold()
    text_value = re.sub(r"\s+", "", text_value)
    for token in ("株式会社", "有限会社", "合同会社", "（株）", "(株)", "㈱"):
        text_value = text_value.replace(token.casefold(), "")
    return text_value.strip()


def ensure_customer_master_table(db: Session) -> None:
    ensure_tlc_code_tables(db)
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id VARCHAR(64) PRIMARY KEY,
            customer_id VARCHAR(128) NOT NULL UNIQUE,
            formal_name VARCHAR(500) NOT NULL,
            hiragana_name VARCHAR(500) NOT NULL DEFAULT '',
            katakana_name VARCHAR(500) NOT NULL DEFAULT '',
            katakana_name_short VARCHAR(500) NOT NULL DEFAULT '',
            delivery_name_1 VARCHAR(500) NOT NULL DEFAULT '',
            delivery_name_2 VARCHAR(500) NOT NULL DEFAULT '',
            short_name VARCHAR(500) NOT NULL DEFAULT '',
            alias_1 VARCHAR(500) NOT NULL DEFAULT '',
            alias_2 VARCHAR(500) NOT NULL DEFAULT '',
            alias_3 VARCHAR(500) NOT NULL DEFAULT '',
            alias_4 VARCHAR(500) NOT NULL DEFAULT '',
            alias_5 VARCHAR(500) NOT NULL DEFAULT '',
            normalized_formal_name VARCHAR(500) NOT NULL DEFAULT '',
            status_code VARCHAR(128) NOT NULL DEFAULT 'ACTIVE',
            active INTEGER NOT NULL DEFAULT 1,
            note TEXT NOT NULL DEFAULT '',
            created_at VARCHAR(64) NOT NULL,
            updated_at VARCHAR(64) NOT NULL
        )
    """))
    existing = {
        row._mapping["name"]
        for row in db.execute(text(f"PRAGMA table_info({TABLE_NAME})")).all()
    }
    for column in ("katakana_name_short", "delivery_name_1", "delivery_name_2"):
        if column not in existing:
            db.execute(text(
                f"ALTER TABLE {TABLE_NAME} ADD COLUMN {column} "
                "VARCHAR(500) NOT NULL DEFAULT ''"
            ))
    db.commit()


def _row(row: Any) -> dict[str, Any]:
    result = dict(row._mapping if hasattr(row, "_mapping") else row)
    result["active"] = bool(result.get("active", 0))
    result["aliases"] = [
        result.get("formal_name", ""),
        result.get("hiragana_name", ""),
        result.get("katakana_name", ""),
        result.get("short_name", ""),
        result.get("alias_1", ""),
        result.get("alias_2", ""),
        result.get("alias_3", ""),
        result.get("alias_4", ""),
        result.get("alias_5", ""),
    ]
    result["aliases"] = [value for value in result["aliases"] if value]
    return result


def list_customers(
    db: Session,
    *,
    query: str = "",
    status_code: str = "",
    include_inactive: bool = True,
    limit: int = 500,
) -> list[dict[str, Any]]:
    ensure_customer_master_table(db)

    clauses = []
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 1000)}

    if query:
        normalized = normalize_customer_name(query)
        clauses.append(
            """(
                customer_id LIKE :query_like
                OR normalized_formal_name LIKE :normalized_like
                OR formal_name LIKE :query_like
                OR hiragana_name LIKE :query_like
                OR katakana_name LIKE :query_like
                OR katakana_name_short LIKE :query_like
                OR delivery_name_1 LIKE :query_like
                OR delivery_name_2 LIKE :query_like
                OR short_name LIKE :query_like
                OR alias_1 LIKE :query_like OR alias_2 LIKE :query_like
                OR alias_3 LIKE :query_like OR alias_4 LIKE :query_like
                OR alias_5 LIKE :query_like
            )"""
        )
        params["query_like"] = f"%{query}%"
        params["normalized_like"] = f"%{normalized}%"

    if status_code:
        clauses.append("status_code = :status_code")
        params["status_code"] = status_code

    if not include_inactive:
        clauses.append("active = 1")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(text(f"""
        SELECT * FROM {TABLE_NAME}
        {where}
        ORDER BY customer_id
        LIMIT :limit
    """), params).all()

    return [_row(row) for row in rows]


def _get_customer_no_ensure(
    db: Session,
    record_id: str,
) -> dict[str, Any] | None:
    row = db.execute(
        text(f"SELECT * FROM {TABLE_NAME} WHERE id=:id"),
        {"id": record_id},
    ).first()
    return _row(row) if row else None


def get_customer(db: Session, record_id: str) -> dict[str, Any] | None:
    ensure_customer_master_table(db)
    return _get_customer_no_ensure(db, record_id)


def _candidate_names(payload: dict[str, Any]) -> list[str]:
    fields = [
        "formal_name", "hiragana_name", "katakana_name", "short_name",
        "alias_1", "alias_2", "alias_3", "alias_4", "alias_5",
    ]
    return [str(payload.get(field, "") or "").strip() for field in fields if str(payload.get(field, "") or "").strip()]


def _check_name_conflicts(db: Session, payload: dict[str, Any], record_id: str = "") -> None:
    candidates = {normalize_customer_name(value) for value in _candidate_names(payload)}
    candidates.discard("")
    if not candidates:
        return

    rows = db.execute(text(f"SELECT * FROM {TABLE_NAME}")).all()
    for row in rows:
        item = _row(row)
        if record_id and item["id"] == record_id:
            continue
        existing = {normalize_customer_name(value) for value in item["aliases"]}
        overlap = candidates & existing
        if overlap:
            raise ValueError(
                f"customer name or alias conflicts with customer_id {item['customer_id']}"
            )


def _active_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value if value is not None else "1").strip().lower() not in {
        "0", "false", "no", "n", "inactive", "停用",
    }


def _save_customer(db: Session, payload: dict[str, Any], *, commit: bool) -> dict[str, Any]:
    customer_id = str(payload.get("customer_id", "") or "").strip()
    formal_name = str(payload.get("formal_name", "") or "").strip()
    if not customer_id:
        raise ValueError("customer_id is required")
    if not formal_name:
        raise ValueError("formal_name is required")

    status_code = str(payload.get("status_code", "ACTIVE") or "ACTIVE").strip().upper()
    record_id = str(payload.get("id", "") or "").strip()

    duplicate = db.execute(
        text(f"SELECT id FROM {TABLE_NAME} WHERE customer_id=:customer_id"),
        {"customer_id": customer_id},
    ).first()

    if duplicate and duplicate._mapping["id"] != record_id:
        raise ValueError("customer_id already exists")

    _check_name_conflicts(db, payload, record_id)

    now = datetime.now(timezone.utc).isoformat()
    params = {
        "customer_id": customer_id,
        "formal_name": formal_name,
        "hiragana_name": str(payload.get("hiragana_name", "") or "").strip(),
        "katakana_name": str(payload.get("katakana_name", "") or "").strip(),
        "katakana_name_short": str(payload.get("katakana_name_short", "") or "").strip(),
        "delivery_name_1": str(payload.get("delivery_name_1", "") or "").strip(),
        "delivery_name_2": str(payload.get("delivery_name_2", "") or "").strip(),
        "short_name": str(payload.get("short_name", "") or "").strip(),
        "alias_1": str(payload.get("alias_1", "") or "").strip(),
        "alias_2": str(payload.get("alias_2", "") or "").strip(),
        "alias_3": str(payload.get("alias_3", "") or "").strip(),
        "alias_4": str(payload.get("alias_4", "") or "").strip(),
        "alias_5": str(payload.get("alias_5", "") or "").strip(),
        "normalized_formal_name": normalize_customer_name(formal_name),
        "status_code": status_code,
        "active": 1 if _active_value(payload.get("active", True)) else 0,
        "note": str(payload.get("note", "") or ""),
        "updated_at": now,
    }

    if record_id:
        params["id"] = record_id
        updated = db.execute(text(f"""
            UPDATE {TABLE_NAME}
            SET customer_id=:customer_id, formal_name=:formal_name,
                hiragana_name=:hiragana_name, katakana_name=:katakana_name,
                katakana_name_short=:katakana_name_short,
                delivery_name_1=:delivery_name_1, delivery_name_2=:delivery_name_2,
                short_name=:short_name, alias_1=:alias_1, alias_2=:alias_2,
                alias_3=:alias_3, alias_4=:alias_4, alias_5=:alias_5,
                normalized_formal_name=:normalized_formal_name,
                status_code=:status_code, active=:active, note=:note,
                updated_at=:updated_at
            WHERE id=:id
        """), params)
        if updated.rowcount == 0:
            raise LookupError("Customer not found")
    else:
        record_id = uuid4().hex
        params.update({"id": record_id, "created_at": now})
        db.execute(text(f"""
            INSERT INTO {TABLE_NAME} (
                id, customer_id, formal_name, hiragana_name, katakana_name,
                katakana_name_short, delivery_name_1, delivery_name_2,
                short_name, alias_1, alias_2, alias_3, alias_4, alias_5,
                normalized_formal_name, status_code, active, note,
                created_at, updated_at
            ) VALUES (
                :id, :customer_id, :formal_name, :hiragana_name, :katakana_name,
                :katakana_name_short, :delivery_name_1, :delivery_name_2,
                :short_name, :alias_1, :alias_2, :alias_3, :alias_4, :alias_5,
                :normalized_formal_name, :status_code, :active, :note,
                :created_at, :updated_at
            )
        """), params)

    if commit:
        db.commit()
    return _get_customer_no_ensure(db, record_id)


def save_customer(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_customer_master_table(db)
    return _save_customer(db, payload, commit=True)


def import_customer_rows(db: Session, rows: list[dict[str, Any]]) -> dict[str, Any]:
    ensure_customer_master_table(db)
    if not rows:
        raise ValueError("import rows are empty")
    if len(rows) > 5000:
        raise ValueError("maximum import size is 5000 rows")

    created = 0
    updated = 0
    try:
        for index, raw in enumerate(rows, start=2):
            if not isinstance(raw, dict):
                raise ValueError(f"CSV row {index}: invalid row")
            payload = {field: raw.get(field, "") for field in EXPORT_FIELDS}
            customer_id = str(payload.get("customer_id", "") or "").strip()
            if not customer_id:
                raise ValueError(f"CSV row {index}: customer_id is required")

            existing = db.execute(
                text(f"SELECT id FROM {TABLE_NAME} WHERE customer_id=:customer_id"),
                {"customer_id": customer_id},
            ).first()
            if existing:
                payload["id"] = existing._mapping["id"]
                updated += 1
            else:
                created += 1
            _save_customer(db, payload, commit=False)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "imported": created + updated,
        "created": created,
        "updated": updated,
    }


def _decode_todokedl_csv(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp932"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV encoding must be UTF-8 or CP932/Shift-JIS")


def import_todokedl_csv_base64(db: Session, content_base64: str) -> dict[str, Any]:
    """Import delivery master fields without overwriting formal customer names."""
    ensure_customer_master_table(db)
    try:
        content = base64.b64decode(content_base64, validate=True)
    except Exception as exc:
        raise ValueError("invalid CSV content") from exc
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("CSV file exceeds 10 MB")

    reader = csv.DictReader(io.StringIO(_decode_todokedl_csv(content)))
    headers = set(reader.fieldnames or [])
    missing = [name for name in TODOKEDL_FIELDS if name not in headers]
    if missing:
        raise ValueError("missing TODOKEDL columns: " + ", ".join(missing))

    created = updated = skipped = 0
    try:
        for index, raw in enumerate(reader, start=2):
            customer_id = str(raw.get("お届け先コード", "") or "").strip()
            if not customer_id:
                if not any(str(value or "").strip() for value in raw.values()):
                    skipped += 1
                    continue
                raise ValueError(f"CSV row {index}: お届け先コード is required")

            delivery = {
                internal: str(raw.get(source, "") or "").strip()
                for source, internal in TODOKEDL_FIELDS.items()
                if internal != "customer_id"
            }
            existing = db.execute(
                text(f"SELECT id FROM {TABLE_NAME} WHERE customer_id=:customer_id"),
                {"customer_id": customer_id},
            ).first()
            now = datetime.now(timezone.utc).isoformat()
            if existing:
                # Empty CSV cells do not erase existing delivery data.
                assignments = []
                params: dict[str, Any] = {"id": existing._mapping["id"], "updated_at": now}
                for field, value in delivery.items():
                    if value:
                        assignments.append(f"{field}=:{field}")
                        params[field] = value
                if assignments:
                    assignments.append("updated_at=:updated_at")
                    db.execute(text(
                        f"UPDATE {TABLE_NAME} SET {', '.join(assignments)} WHERE id=:id"
                    ), params)
                updated += 1
            else:
                record_id = uuid4().hex
                db.execute(text(f"""
                    INSERT INTO {TABLE_NAME} (
                        id, customer_id, formal_name, hiragana_name, katakana_name,
                        katakana_name_short, delivery_name_1, delivery_name_2,
                        short_name, alias_1, alias_2, alias_3, alias_4, alias_5,
                        normalized_formal_name, status_code, active, note,
                        created_at, updated_at
                    ) VALUES (
                        :id, :customer_id, '', '', '',
                        :katakana_name_short, :delivery_name_1, :delivery_name_2,
                        '', '', '', '', '', '', '', 'ACTIVE', 1,
                        'TODOKEDL import: formal customer name pending maintenance',
                        :created_at, :updated_at
                    )
                """), {
                    "id": record_id,
                    "customer_id": customer_id,
                    **delivery,
                    "created_at": now,
                    "updated_at": now,
                })
                created += 1
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"imported": created + updated, "created": created, "updated": updated, "skipped": skipped}


def export_customers_csv(
    db: Session,
    *,
    query: str = "",
    status_code: str = "",
    include_inactive: bool = True,
) -> bytes:
    rows = list_customers(
        db,
        query=query,
        status_code=status_code,
        include_inactive=include_inactive,
        limit=1000,
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        item = {field: row.get(field, "") for field in EXPORT_FIELDS}
        item["active"] = "1" if row.get("active") else "0"
        writer.writerow(item)
    return ("\ufeff" + output.getvalue()).encode("utf-8")

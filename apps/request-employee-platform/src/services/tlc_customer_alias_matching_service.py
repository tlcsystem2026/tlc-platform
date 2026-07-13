
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


MATCH_TABLE = "tlc_customer_alias_match_result"
CUSTOMER_TABLE_CANDIDATES = [
    "tlc_customer_master",
    "tlc_customer",
    "customer_master",
]

FIELD_CANDIDATES = {
    "customer_id": ("customer_id", "customer_code", "id"),
    "formal_name": ("formal_name", "customer_name", "name"),
    "hiragana_name": ("hiragana_name", "hiragana"),
    "katakana_name": ("katakana_name", "katakana"),
    "short_name": ("short_name", "abbreviation", "abbr_name"),
    "alias_1": ("alias_1", "alias1"),
    "alias_2": ("alias_2", "alias2"),
    "alias_3": ("alias_3", "alias3"),
    "alias_4": ("alias_4", "alias4"),
    "alias_5": ("alias_5", "alias5"),
    "active": ("active", "is_active"),
    "status_code": ("status_code", "status"),
}

COMPANY_TOKENS = (
    "株式会社",
    "有限会社",
    "合同会社",
    "合資会社",
    "合名会社",
    "(株)",
    "（株）",
    "㈱",
    "(有)",
    "（有）",
    "㈲",
    "inc",
    "inc.",
    "ltd",
    "ltd.",
    "co",
    "co.",
    "corp",
    "corp.",
    "corporation",
    "company",
)


def ensure_table(db: Session) -> None:
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {MATCH_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            raw_name VARCHAR(1000) NOT NULL,
            normalized_name VARCHAR(1000) NOT NULL,
            match_status VARCHAR(64) NOT NULL,
            match_level VARCHAR(64) NOT NULL DEFAULT '',
            customer_id VARCHAR(255) NOT NULL DEFAULT '',
            customer_name VARCHAR(500) NOT NULL DEFAULT '',
            matched_field VARCHAR(128) NOT NULL DEFAULT '',
            matched_value VARCHAR(1000) NOT NULL DEFAULT '',
            match_score INTEGER NOT NULL DEFAULT 0,
            candidate_count INTEGER NOT NULL DEFAULT 0,
            candidate_json TEXT NOT NULL DEFAULT '[]',
            manual_override INTEGER NOT NULL DEFAULT 0,
            operator VARCHAR(255) NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            created_at VARCHAR(64) NOT NULL,
            updated_at VARCHAR(64) NOT NULL
        )
    """))
    db.commit()


def normalize_customer_name(value: str) -> str:
    text_value = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text_value = text_value.replace("ヴ", "ブ")
    for token in COMPANY_TOKENS:
        text_value = text_value.replace(token, "")
    text_value = re.sub(r"[\s\u3000・･\-‐‑‒–—―_.,，。/／\\()（）\[\]【】「」『』]+", "", text_value)
    text_value = re.sub(r"[^\wぁ-んァ-ヶ一-龠々ー]", "", text_value)
    return text_value


def _table_exists(db: Session, table_name: str) -> bool:
    return db.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name=:table_name"
        ),
        {"table_name": table_name},
    ).first() is not None


def _columns(db: Session, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in db.execute(text(f"PRAGMA table_info({table_name})")).all()
    }


def _first(columns: set[str], candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return ""


def _discover_customer_source(db: Session) -> tuple[str, dict[str, str]]:
    for table_name in CUSTOMER_TABLE_CANDIDATES:
        if not _table_exists(db, table_name):
            continue
        columns = _columns(db, table_name)
        mapping = {
            key: _first(columns, candidates)
            for key, candidates in FIELD_CANDIDATES.items()
        }
        if mapping["customer_id"] and mapping["formal_name"]:
            return table_name, mapping
    raise ValueError("Customer master table not found")


def _customer_rows(
    db: Session,
    table_name: str,
    mapping: dict[str, str],
) -> list[dict[str, Any]]:
    selected = []
    for key, column in mapping.items():
        if column:
            selected.append(f"{column} AS {key}")
        else:
            selected.append(f"'' AS {key}")

    where = []
    if mapping.get("active"):
        where.append(f"COALESCE({mapping['active']},1)<>0")
    if mapping.get("status_code"):
        where.append(
            f"UPPER(COALESCE({mapping['status_code']},'ACTIVE')) "
            "NOT IN ('INACTIVE','DISABLED','DELETED')"
        )

    sql = (
        f"SELECT {', '.join(selected)} FROM {table_name} "
        + (f"WHERE {' AND '.join(where)}" if where else "")
    )
    return [dict(row._mapping) for row in db.execute(text(sql)).all()]


def _build_index(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    ordered_fields = [
        ("formal_name", "EXACT", 100),
        ("alias_1", "ALIAS", 98),
        ("alias_2", "ALIAS", 98),
        ("alias_3", "ALIAS", 98),
        ("alias_4", "ALIAS", 98),
        ("alias_5", "ALIAS", 98),
        ("short_name", "SHORT_NAME", 95),
        ("katakana_name", "KATAKANA", 94),
        ("hiragana_name", "HIRAGANA", 93),
    ]

    for row in rows:
        for field_name, match_level, score in ordered_fields:
            raw = str(row.get(field_name) or "").strip()
            if not raw:
                continue
            normalized = normalize_customer_name(raw)
            if not normalized:
                continue
            index.setdefault(normalized, []).append(
                {
                    "customer_id": str(row.get("customer_id") or ""),
                    "customer_name": str(row.get("formal_name") or ""),
                    "matched_field": field_name,
                    "matched_value": raw,
                    "match_level": match_level,
                    "match_score": score,
                }
            )
    return index


def match_customer_name(
    db: Session,
    *,
    raw_name: str,
    operator: str = "",
    save_result: bool = True,
) -> dict[str, Any]:
    ensure_table(db)

    raw_name = str(raw_name or "").strip()
    if not raw_name:
        raise ValueError("raw_name is required")

    table_name, mapping = _discover_customer_source(db)
    rows = _customer_rows(db, table_name, mapping)
    index = _build_index(rows)
    normalized = normalize_customer_name(raw_name)

    candidates = index.get(normalized, [])
    unique_by_customer: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        customer_id = candidate["customer_id"]
        existing = unique_by_customer.get(customer_id)
        if existing is None or candidate["match_score"] > existing["match_score"]:
            unique_by_customer[customer_id] = candidate

    unique_candidates = sorted(
        unique_by_customer.values(),
        key=lambda item: (-item["match_score"], item["customer_id"]),
    )

    if not unique_candidates:
        result = {
            "raw_name": raw_name,
            "normalized_name": normalized,
            "match_status": "UNMATCHED",
            "match_level": "",
            "customer_id": "",
            "customer_name": "",
            "matched_field": "",
            "matched_value": "",
            "match_score": 0,
            "candidate_count": 0,
            "candidates": [],
            "manual_override": False,
        }
    elif len(unique_candidates) == 1:
        candidate = unique_candidates[0]
        result = {
            "raw_name": raw_name,
            "normalized_name": normalized,
            "match_status": "MATCHED",
            "match_level": candidate["match_level"],
            "customer_id": candidate["customer_id"],
            "customer_name": candidate["customer_name"],
            "matched_field": candidate["matched_field"],
            "matched_value": candidate["matched_value"],
            "match_score": candidate["match_score"],
            "candidate_count": 1,
            "candidates": unique_candidates,
            "manual_override": False,
        }
    else:
        result = {
            "raw_name": raw_name,
            "normalized_name": normalized,
            "match_status": "AMBIGUOUS",
            "match_level": "",
            "customer_id": "",
            "customer_name": "",
            "matched_field": "",
            "matched_value": "",
            "match_score": max(item["match_score"] for item in unique_candidates),
            "candidate_count": len(unique_candidates),
            "candidates": unique_candidates,
            "manual_override": False,
        }

    if save_result:
        import json
        now = datetime.now(timezone.utc).isoformat()
        result_id = uuid4().hex
        db.execute(text(f"""
            INSERT INTO {MATCH_TABLE} (
                id, raw_name, normalized_name,
                match_status, match_level,
                customer_id, customer_name,
                matched_field, matched_value,
                match_score, candidate_count,
                candidate_json, manual_override,
                operator, note, created_at, updated_at
            ) VALUES (
                :id, :raw_name, :normalized_name,
                :match_status, :match_level,
                :customer_id, :customer_name,
                :matched_field, :matched_value,
                :match_score, :candidate_count,
                :candidate_json, 0,
                :operator, '', :created_at, :updated_at
            )
        """), {
            "id": result_id,
            "raw_name": result["raw_name"],
            "normalized_name": result["normalized_name"],
            "match_status": result["match_status"],
            "match_level": result["match_level"],
            "customer_id": result["customer_id"],
            "customer_name": result["customer_name"],
            "matched_field": result["matched_field"],
            "matched_value": result["matched_value"],
            "match_score": result["match_score"],
            "candidate_count": result["candidate_count"],
            "candidate_json": json.dumps(
                result["candidates"],
                ensure_ascii=False,
            ),
            "operator": str(operator or ""),
            "created_at": now,
            "updated_at": now,
        })
        db.commit()
        result["id"] = result_id

    result["customer_source_table"] = table_name
    return result


def override_match_result(
    db: Session,
    *,
    result_id: str,
    customer_id: str,
    operator: str,
    note: str = "",
) -> dict[str, Any]:
    ensure_table(db)
    operator = str(operator or "").strip()
    customer_id = str(customer_id or "").strip()
    if not operator:
        raise ValueError("operator is required")
    if not customer_id:
        raise ValueError("customer_id is required")

    current = db.execute(
        text(f"SELECT * FROM {MATCH_TABLE} WHERE id=:id"),
        {"id": result_id},
    ).first()
    if not current:
        raise LookupError("Match result not found")

    table_name, mapping = _discover_customer_source(db)
    row = db.execute(
        text(
            f"SELECT {mapping['formal_name']} AS formal_name "
            f"FROM {table_name} "
            f"WHERE {mapping['customer_id']}=:customer_id"
        ),
        {"customer_id": customer_id},
    ).first()
    if not row:
        raise LookupError("Customer not found")

    now = datetime.now(timezone.utc).isoformat()
    db.execute(text(f"""
        UPDATE {MATCH_TABLE}
        SET match_status='MATCHED',
            match_level='MANUAL',
            customer_id=:customer_id,
            customer_name=:customer_name,
            matched_field='manual_override',
            matched_value=:customer_name,
            match_score=100,
            candidate_count=1,
            manual_override=1,
            operator=:operator,
            note=:note,
            updated_at=:updated_at
        WHERE id=:id
    """), {
        "id": result_id,
        "customer_id": customer_id,
        "customer_name": str(row[0] or ""),
        "operator": operator,
        "note": str(note or ""),
        "updated_at": now,
    })
    db.commit()

    updated = db.execute(
        text(f"SELECT * FROM {MATCH_TABLE} WHERE id=:id"),
        {"id": result_id},
    ).first()
    return dict(updated._mapping)


def list_match_results(
    db: Session,
    *,
    status: str = "",
    limit: int = 200,
) -> list[dict[str, Any]]:
    ensure_table(db)
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 1000)}
    where = ""
    if status:
        normalized = status.strip().upper()
        if normalized not in {"MATCHED", "AMBIGUOUS", "UNMATCHED"}:
            raise ValueError("Unsupported match status")
        where = "WHERE match_status=:status"
        params["status"] = normalized

    rows = db.execute(
        text(
            f"SELECT * FROM {MATCH_TABLE} "
            f"{where} ORDER BY created_at DESC LIMIT :limit"
        ),
        params,
    ).all()
    return [dict(row._mapping) for row in rows]

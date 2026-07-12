from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_customer_master_service import (
    TABLE_NAME as CUSTOMER_TABLE,
    ensure_customer_master_table,
)


MATCH_FIELDS = (
    "formal_name",
    "hiragana_name",
    "katakana_name",
    "short_name",
    "alias_1",
    "alias_2",
    "alias_3",
    "alias_4",
    "alias_5",
)

CORPORATE_TOKENS = (
    "株式会社",
    "有限会社",
    "合同会社",
    "合資会社",
    "合名会社",
    "一般社団法人",
    "一般財団法人",
    "公益社団法人",
    "公益財団法人",
    "医療法人",
    "学校法人",
    "社会福祉法人",
    "宗教法人",
    "特定非営利活動法人",
    "（株）",
    "(株)",
    "㈱",
    "（有）",
    "(有)",
    "㈲",
)


@dataclass(slots=True)
class CustomerNameMatch:
    status: str
    counterparty: str
    normalized_counterparty: str
    customer_id: str = ""
    customer_record_id: str = ""
    matched_field: str = ""
    matched_value: str = ""
    candidates: list[dict[str, str]] | None = None

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["candidates"] = result["candidates"] or []
        return result


def normalize_bank_counterparty(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = normalized.casefold()
    normalized = re.sub(r"\s+", "", normalized)

    # Remove corporate suffixes before punctuation. NFKC changes （株） to (株),
    # so removing brackets first would incorrectly leave a trailing "株".
    normalized_tokens = sorted(
        {
            unicodedata.normalize("NFKC", token).casefold()
            for token in CORPORATE_TOKENS
        },
        key=len,
        reverse=True,
    )
    for token in normalized_tokens:
        normalized = normalized.replace(token, "")

    normalized = re.sub(r"[・･.,，。'\"`´’‘“”\-_/\\()（）\[\]【】]", "", normalized)

    # Run once more for defensive handling of punctuation-separated variants.
    for token in normalized_tokens:
        normalized = normalized.replace(token, "")

    return normalized.strip()


def _customer_rows(db: Session) -> list[dict[str, Any]]:
    ensure_customer_master_table(db)
    rows = db.execute(text(f"""
        SELECT *
        FROM {CUSTOMER_TABLE}
        WHERE active = 1
        ORDER BY customer_id
    """)).all()
    return [dict(row._mapping) for row in rows]


def match_customer_by_bank_counterparty(
    db: Session,
    counterparty: str,
) -> CustomerNameMatch:
    normalized_counterparty = normalize_bank_counterparty(counterparty)

    if not normalized_counterparty:
        return CustomerNameMatch(
            status="UNMATCHED",
            counterparty=str(counterparty or ""),
            normalized_counterparty="",
        )

    matches: list[dict[str, str]] = []

    for customer in _customer_rows(db):
        for field in MATCH_FIELDS:
            value = str(customer.get(field, "") or "").strip()
            if not value:
                continue

            normalized_value = normalize_bank_counterparty(value)
            if normalized_value and normalized_value == normalized_counterparty:
                matches.append(
                    {
                        "customer_id": str(customer["customer_id"]),
                        "customer_record_id": str(customer["id"]),
                        "matched_field": field,
                        "matched_value": value,
                    }
                )

    unique_customers: dict[str, dict[str, str]] = {}
    for match in matches:
        unique_customers.setdefault(match["customer_record_id"], match)

    candidates = list(unique_customers.values())

    if not candidates:
        return CustomerNameMatch(
            status="UNMATCHED",
            counterparty=str(counterparty or ""),
            normalized_counterparty=normalized_counterparty,
        )

    if len(candidates) > 1:
        return CustomerNameMatch(
            status="AMBIGUOUS",
            counterparty=str(counterparty or ""),
            normalized_counterparty=normalized_counterparty,
            candidates=candidates,
        )

    candidate = candidates[0]
    return CustomerNameMatch(
        status="MATCHED",
        counterparty=str(counterparty or ""),
        normalized_counterparty=normalized_counterparty,
        customer_id=candidate["customer_id"],
        customer_record_id=candidate["customer_record_id"],
        matched_field=candidate["matched_field"],
        matched_value=candidate["matched_value"],
        candidates=candidates,
    )


def match_unassigned_bank_transactions(
    db: Session,
    *,
    limit: int = 500,
) -> dict[str, Any]:
    ensure_customer_master_table(db)

    bank_table_exists = db.execute(text("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='bank_transaction_import'
    """)).first()
    if not bank_table_exists:
        return {
            "processed": 0,
            "matched": 0,
            "unmatched": 0,
            "ambiguous": 0,
            "results": [],
        }

    columns = {
        row[1]
        for row in db.execute(text("PRAGMA table_info(bank_transaction_import)")).all()
    }

    if "matched_customer_id" not in columns:
        db.execute(text(
            "ALTER TABLE bank_transaction_import "
            "ADD COLUMN matched_customer_id VARCHAR(128) NOT NULL DEFAULT ''"
        ))
    if "customer_match_status" not in columns:
        db.execute(text(
            "ALTER TABLE bank_transaction_import "
            "ADD COLUMN customer_match_status VARCHAR(32) NOT NULL DEFAULT ''"
        ))
    if "customer_match_field" not in columns:
        db.execute(text(
            "ALTER TABLE bank_transaction_import "
            "ADD COLUMN customer_match_field VARCHAR(64) NOT NULL DEFAULT ''"
        ))
    db.commit()

    safe_limit = min(max(int(limit), 1), 1000)

    rows = db.execute(text("""
        SELECT id, counterparty
        FROM bank_transaction_import
        WHERE direction='CREDIT'
        ORDER BY transaction_date, imported_at
        LIMIT :limit
    """), {"limit": safe_limit}).all()

    results: list[dict[str, Any]] = []
    counts = {"MATCHED": 0, "UNMATCHED": 0, "AMBIGUOUS": 0}

    for row in rows:
        tx_id = row._mapping["id"]
        counterparty = row._mapping["counterparty"]
        match = match_customer_by_bank_counterparty(db, counterparty)
        counts[match.status] += 1

        db.execute(text("""
            UPDATE bank_transaction_import
            SET matched_customer_id=:customer_id,
                customer_match_status=:status,
                customer_match_field=:field
            WHERE id=:id
        """), {
            "id": tx_id,
            "customer_id": match.customer_id,
            "status": match.status,
            "field": match.matched_field,
        })

        results.append({
            "bank_transaction_id": tx_id,
            **match.as_dict(),
        })

    db.commit()

    return {
        "processed": len(results),
        "matched": counts["MATCHED"],
        "unmatched": counts["UNMATCHED"],
        "ambiguous": counts["AMBIGUOUS"],
        "results": results,
    }

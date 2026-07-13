
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


BANK_TABLE_CANDIDATES = [
    "tlc_bank_transaction",
    "tlc_bank_statement_entry",
    "tlc_bank_import_row",
    "tlc_bank_csv_row",
    "bank_transaction",
]

FIELD_CANDIDATES = {
    "id": ("id", "entry_id", "transaction_id", "row_id"),
    "customer_id": (
        "customer_id",
        "customer_code",
        "client_id",
        "account_customer_id",
        "matched_customer_id",
    ),
    "customer_name": (
        "customer_name",
        "formal_name",
        "client_name",
        "counterparty_name",
        "matched_customer_name",
    ),
    "business_date": (
        "business_date",
        "transaction_date",
        "value_date",
        "posted_date",
        "booking_date",
        "date",
    ),
    "amount": (
        "payment_amount",
        "deposit_amount",
        "credit_amount",
        "incoming_amount",
        "amount",
    ),
    "bank_name": (
        "bank_name",
        "financial_institution_name",
        "source_bank_name",
    ),
    "account_name": (
        "account_name",
        "account_holder",
        "counterparty_account_name",
        "payer_name",
    ),
    "summary": (
        "summary",
        "description",
        "memo",
        "remark",
        "transaction_description",
    ),
    "reference_no": (
        "reference_no",
        "transaction_no",
        "bank_reference",
        "document_no",
    ),
    "direction": (
        "direction",
        "transaction_type",
        "debit_credit",
        "entry_type",
    ),
    "batch_id": ("batch_id",),
    "status": ("status", "match_status", "transaction_status"),
}


def _table_exists(db: Session, table_name: str) -> bool:
    return db.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name=:table_name"
        ),
        {"table_name": table_name},
    ).first() is not None


def _columns(db: Session, table_name: str) -> set[str]:
    if not _table_exists(db, table_name):
        return set()
    return {
        str(row[1])
        for row in db.execute(
            text(f"PRAGMA table_info({table_name})")
        ).all()
    }


def _first(columns: set[str], candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return ""


def discover_bank_source(db: Session) -> dict[str, str]:
    for table_name in BANK_TABLE_CANDIDATES:
        columns = _columns(db, table_name)
        if not columns:
            continue
        mapping = {
            key: _first(columns, candidates)
            for key, candidates in FIELD_CANDIDATES.items()
        }
        if (
            mapping["business_date"]
            and mapping["amount"]
            and (
                mapping["customer_id"]
                or mapping["customer_name"]
                or mapping["account_name"]
            )
        ):
            mapping["table"] = table_name
            return mapping
    return {}


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0").replace(",", ""))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _format_decimal(value: Decimal) -> str:
    value = value.quantize(Decimal("0.01"))
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _is_incoming(direction: str) -> bool:
    normalized = str(direction or "").strip().upper()
    if not normalized:
        return True
    return normalized in {
        "CREDIT",
        "CR",
        "IN",
        "INCOMING",
        "DEPOSIT",
        "PAYMENT",
        "入金",
        "振込入金",
    }


def list_bank_payment_evidence(
    db: Session,
    *,
    customer_id: str = "",
    customer_name: str = "",
    previous_cutoff: str,
    current_cutoff: str,
    limit: int = 1000,
) -> dict[str, Any]:
    customer_id = str(customer_id or "").strip()
    customer_name = str(customer_name or "").strip()
    previous_cutoff = str(previous_cutoff or "").strip()
    current_cutoff = str(current_cutoff or "").strip()

    if not customer_id and not customer_name:
        raise ValueError("customer_id or customer_name is required")
    if not previous_cutoff or not current_cutoff:
        raise ValueError("cutoff dates are required")
    if current_cutoff <= previous_cutoff:
        raise ValueError("current cutoff must be after previous cutoff")

    source = discover_bank_source(db)
    if not source:
        return {
            "source_table": "",
            "customer_id": customer_id,
            "customer_name": customer_name,
            "previous_cutoff": previous_cutoff,
            "current_cutoff": current_cutoff,
            "record_count": 0,
            "payment_total": "0",
            "records": [],
        }

    select_parts = []
    for key in [
        "id",
        "customer_id",
        "customer_name",
        "business_date",
        "amount",
        "bank_name",
        "account_name",
        "summary",
        "reference_no",
        "direction",
        "batch_id",
        "status",
    ]:
        column = source.get(key, "")
        if column:
            select_parts.append(f"{column} AS {key}")
        else:
            select_parts.append(f"'' AS {key}")

    filters = [
        f"{source['business_date']} > :previous_cutoff",
        f"{source['business_date']} <= :current_cutoff",
    ]
    params: dict[str, Any] = {
        "previous_cutoff": previous_cutoff,
        "current_cutoff": current_cutoff,
        "limit": min(max(int(limit), 1), 5000),
    }

    identity_filters = []
    if source.get("customer_id") and customer_id:
        identity_filters.append(
            f"{source['customer_id']}=:customer_id"
        )
        params["customer_id"] = customer_id
    if source.get("customer_name") and customer_name:
        identity_filters.append(
            f"{source['customer_name']}=:customer_name"
        )
        params["customer_name"] = customer_name
    if source.get("account_name") and customer_name:
        identity_filters.append(
            f"{source['account_name']}=:customer_name"
        )
        params["customer_name"] = customer_name

    if not identity_filters:
        return {
            "source_table": source["table"],
            "customer_id": customer_id,
            "customer_name": customer_name,
            "previous_cutoff": previous_cutoff,
            "current_cutoff": current_cutoff,
            "record_count": 0,
            "payment_total": "0",
            "records": [],
        }

    filters.append("(" + " OR ".join(identity_filters) + ")")

    order_id = source.get("id") or source["business_date"]

    rows = db.execute(
        text(
            f"SELECT {', '.join(select_parts)} "
            f"FROM {source['table']} "
            f"WHERE {' AND '.join(filters)} "
            f"ORDER BY {source['business_date']}, {order_id} "
            "LIMIT :limit"
        ),
        params,
    ).all()

    records = []
    total = Decimal("0")
    for row in rows:
        item = dict(row._mapping)
        if not _is_incoming(item.get("direction", "")):
            continue
        amount = _decimal(item.get("amount"))
        total += amount
        item["amount"] = _format_decimal(amount)
        records.append(item)

    return {
        "source_table": source["table"],
        "customer_id": customer_id,
        "customer_name": customer_name,
        "previous_cutoff": previous_cutoff,
        "current_cutoff": current_cutoff,
        "record_count": len(records),
        "payment_total": _format_decimal(total),
        "records": records,
    }


def compare_snapshot_payments(
    db: Session,
    *,
    snapshot_id: str,
    limit: int = 1000,
) -> dict[str, Any]:
    if not _table_exists(db, "tlc_customer_reconciliation_snapshot"):
        raise LookupError("Reconciliation snapshot table not found")

    snapshot = db.execute(
        text(
            "SELECT * FROM tlc_customer_reconciliation_snapshot "
            "WHERE id=:id"
        ),
        {"id": snapshot_id},
    ).first()
    if not snapshot:
        raise LookupError("Reconciliation snapshot not found")

    snapshot_data = dict(snapshot._mapping)
    evidence = list_bank_payment_evidence(
        db,
        customer_id=snapshot_data.get("customer_id", ""),
        customer_name=snapshot_data.get("customer_name", ""),
        previous_cutoff=snapshot_data["previous_bank_cutoff"],
        current_cutoff=snapshot_data["current_bank_cutoff"],
        limit=limit,
    )

    snapshot_total = _decimal(snapshot_data.get("payment_total"))
    evidence_total = _decimal(evidence.get("payment_total"))
    difference = snapshot_total - evidence_total

    return {
        "snapshot": snapshot_data,
        "evidence": evidence,
        "snapshot_payment_total": _format_decimal(snapshot_total),
        "evidence_payment_total": _format_decimal(evidence_total),
        "difference": _format_decimal(difference),
        "consistent": difference == Decimal("0"),
    }

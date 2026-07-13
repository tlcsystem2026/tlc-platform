
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


SNAPSHOT_TABLE = "tlc_customer_reconciliation_snapshot"

SALES_TABLE_CANDIDATES = [
    "tlc_sales_ledger",
    "tlc_sales_ledger_entry",
    "tlc_sales_request_ledger",
    "sales_ledger",
]

PAYMENT_TABLE_CANDIDATES = [
    "tlc_bank_transaction",
    "tlc_bank_statement_entry",
    "tlc_bank_import_row",
    "bank_transaction",
]

CUSTOMER_ID_COLUMNS = (
    "customer_id",
    "customer_code",
    "client_id",
    "account_customer_id",
)

CUSTOMER_NAME_COLUMNS = (
    "customer_name",
    "formal_name",
    "client_name",
    "counterparty_name",
)

DATE_COLUMNS = (
    "business_date",
    "request_date",
    "sales_date",
    "transaction_date",
    "value_date",
    "posted_date",
    "date",
)

SALES_AMOUNT_COLUMNS = (
    "sales_amount",
    "total_amount",
    "amount",
    "request_amount",
    "invoice_amount",
)

PAYMENT_AMOUNT_COLUMNS = (
    "payment_amount",
    "deposit_amount",
    "credit_amount",
    "incoming_amount",
    "amount",
)


def ensure_table(db: Session) -> None:
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {SNAPSHOT_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            customer_id VARCHAR(255) NOT NULL,
            customer_name VARCHAR(500) NOT NULL DEFAULT '',
            previous_request_cutoff VARCHAR(32) NOT NULL,
            current_request_cutoff VARCHAR(32) NOT NULL,
            previous_bank_cutoff VARCHAR(32) NOT NULL,
            current_bank_cutoff VARCHAR(32) NOT NULL,
            sales_total VARCHAR(64) NOT NULL DEFAULT '0',
            payment_total VARCHAR(64) NOT NULL DEFAULT '0',
            unpaid_amount VARCHAR(64) NOT NULL DEFAULT '0',
            sales_source VARCHAR(255) NOT NULL DEFAULT '',
            payment_source VARCHAR(255) NOT NULL DEFAULT '',
            calculation_rule VARCHAR(255) NOT NULL,
            created_by VARCHAR(255) NOT NULL,
            created_at VARCHAR(64) NOT NULL
        )
    """))
    db.commit()


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


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0").replace(",", ""))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _format_decimal(value: Decimal) -> str:
    value = value.quantize(Decimal("0.01"))
    text_value = format(value, "f")
    return text_value.rstrip("0").rstrip(".") if "." in text_value else text_value


def _validate_range(previous_date: str, current_date: str, label: str) -> None:
    if not previous_date or not current_date:
        raise ValueError(f"{label} cutoff dates are required")
    if current_date <= previous_date:
        raise ValueError(
            f"{label} current cutoff must be after previous cutoff"
        )


def _discover_source(
    db: Session,
    table_candidates: list[str],
    amount_candidates: tuple[str, ...],
) -> dict[str, str]:
    for table_name in table_candidates:
        columns = _columns(db, table_name)
        if not columns:
            continue
        customer_id_column = _first(columns, CUSTOMER_ID_COLUMNS)
        customer_name_column = _first(columns, CUSTOMER_NAME_COLUMNS)
        date_column = _first(columns, DATE_COLUMNS)
        amount_column = _first(columns, amount_candidates)

        if date_column and amount_column and (
            customer_id_column or customer_name_column
        ):
            return {
                "table": table_name,
                "customer_id": customer_id_column,
                "customer_name": customer_name_column,
                "date": date_column,
                "amount": amount_column,
            }
    return {}


def _sum_source(
    db: Session,
    source: dict[str, str],
    *,
    customer_id: str,
    customer_name: str,
    previous_cutoff: str,
    current_cutoff: str,
) -> Decimal:
    if not source:
        return Decimal("0")

    filters = [
        f"{source['date']} > :previous_cutoff",
        f"{source['date']} <= :current_cutoff",
    ]
    params: dict[str, Any] = {
        "previous_cutoff": previous_cutoff,
        "current_cutoff": current_cutoff,
    }

    identity_filters = []
    if source.get("customer_id") and customer_id:
        identity_filters.append(
            f"{source['customer_id']} = :customer_id"
        )
        params["customer_id"] = customer_id

    if source.get("customer_name") and customer_name:
        identity_filters.append(
            f"{source['customer_name']} = :customer_name"
        )
        params["customer_name"] = customer_name

    if not identity_filters:
        return Decimal("0")

    filters.append("(" + " OR ".join(identity_filters) + ")")

    rows = db.execute(
        text(
            f"SELECT {source['amount']} "
            f"FROM {source['table']} "
            f"WHERE {' AND '.join(filters)}"
        ),
        params,
    ).all()

    return sum((_decimal(row[0]) for row in rows), Decimal("0"))


def calculate_snapshot(
    db: Session,
    *,
    customer_id: str,
    customer_name: str,
    previous_request_cutoff: str,
    current_request_cutoff: str,
    previous_bank_cutoff: str,
    current_bank_cutoff: str,
    created_by: str,
) -> dict[str, Any]:
    ensure_table(db)

    customer_id = str(customer_id or "").strip()
    customer_name = str(customer_name or "").strip()
    created_by = str(created_by or "").strip()

    if not customer_id and not customer_name:
        raise ValueError("customer_id or customer_name is required")
    if not created_by:
        raise ValueError("created_by is required")

    _validate_range(
        previous_request_cutoff,
        current_request_cutoff,
        "request",
    )
    _validate_range(
        previous_bank_cutoff,
        current_bank_cutoff,
        "bank",
    )

    sales_source = _discover_source(
        db,
        SALES_TABLE_CANDIDATES,
        SALES_AMOUNT_COLUMNS,
    )
    payment_source = _discover_source(
        db,
        PAYMENT_TABLE_CANDIDATES,
        PAYMENT_AMOUNT_COLUMNS,
    )

    sales_total = _sum_source(
        db,
        sales_source,
        customer_id=customer_id,
        customer_name=customer_name,
        previous_cutoff=previous_request_cutoff,
        current_cutoff=current_request_cutoff,
    )
    payment_total = _sum_source(
        db,
        payment_source,
        customer_id=customer_id,
        customer_name=customer_name,
        previous_cutoff=previous_bank_cutoff,
        current_cutoff=current_bank_cutoff,
    )
    unpaid_amount = sales_total - payment_total

    snapshot_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    calculation_rule = (
        "(previous cutoff, current cutoff] / "
        "unpaid = sales total - payment total"
    )

    db.execute(text(f"""
        INSERT INTO {SNAPSHOT_TABLE} (
            id, customer_id, customer_name,
            previous_request_cutoff, current_request_cutoff,
            previous_bank_cutoff, current_bank_cutoff,
            sales_total, payment_total, unpaid_amount,
            sales_source, payment_source,
            calculation_rule, created_by, created_at
        ) VALUES (
            :id, :customer_id, :customer_name,
            :previous_request_cutoff, :current_request_cutoff,
            :previous_bank_cutoff, :current_bank_cutoff,
            :sales_total, :payment_total, :unpaid_amount,
            :sales_source, :payment_source,
            :calculation_rule, :created_by, :created_at
        )
    """), {
        "id": snapshot_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "previous_request_cutoff": previous_request_cutoff,
        "current_request_cutoff": current_request_cutoff,
        "previous_bank_cutoff": previous_bank_cutoff,
        "current_bank_cutoff": current_bank_cutoff,
        "sales_total": _format_decimal(sales_total),
        "payment_total": _format_decimal(payment_total),
        "unpaid_amount": _format_decimal(unpaid_amount),
        "sales_source": sales_source.get("table", ""),
        "payment_source": payment_source.get("table", ""),
        "calculation_rule": calculation_rule,
        "created_by": created_by,
        "created_at": now,
    })
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {SNAPSHOT_TABLE} WHERE id=:id"),
        {"id": snapshot_id},
    ).first()
    return dict(row._mapping)


def list_snapshots(
    db: Session,
    *,
    customer_id: str = "",
    limit: int = 200,
) -> list[dict[str, Any]]:
    ensure_table(db)

    params: dict[str, Any] = {
        "limit": min(max(int(limit), 1), 1000)
    }
    where = ""
    if customer_id:
        where = "WHERE customer_id=:customer_id"
        params["customer_id"] = customer_id

    rows = db.execute(
        text(
            f"SELECT * FROM {SNAPSHOT_TABLE} "
            f"{where} ORDER BY created_at DESC LIMIT :limit"
        ),
        params,
    ).all()
    return [dict(row._mapping) for row in rows]


def get_snapshot(db: Session, snapshot_id: str) -> dict[str, Any]:
    ensure_table(db)
    row = db.execute(
        text(f"SELECT * FROM {SNAPSHOT_TABLE} WHERE id=:id"),
        {"id": snapshot_id},
    ).first()
    if not row:
        raise LookupError("Reconciliation snapshot not found")
    return dict(row._mapping)

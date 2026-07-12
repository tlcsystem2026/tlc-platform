from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.formal_sales_ledger_service import (
    LEDGER_TABLE,
    ensure_sales_ledger_table,
)
from src.services.multi_bank_csv_import_service import (
    BANK_TABLE,
    ensure_bank_transaction_table,
)


def _decimal(value: Any) -> Decimal:
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return Decimal("0")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


def _money(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return format(normalized.quantize(Decimal("1")), "f")
    return format(normalized, "f")


def _validate_period(previous_cutoff: str, current_cutoff: str, label: str) -> None:
    if not previous_cutoff:
        raise ValueError(f"previous_{label}_cutoff is required")
    if not current_cutoff:
        raise ValueError(f"current_{label}_cutoff is required")
    if previous_cutoff >= current_cutoff:
        raise ValueError(
            f"previous_{label}_cutoff must be earlier than current_{label}_cutoff"
        )


def customer_period_reconciliation(
    db: Session,
    *,
    customer_id: str,
    previous_request_cutoff: str,
    current_request_cutoff: str,
    previous_bank_cutoff: str,
    current_bank_cutoff: str,
) -> dict[str, Any]:
    customer_id = str(customer_id or "").strip()
    if not customer_id:
        raise ValueError("customer_id is required")

    _validate_period(previous_request_cutoff, current_request_cutoff, "request")
    _validate_period(previous_bank_cutoff, current_bank_cutoff, "bank")

    ensure_sales_ledger_table(db)
    ensure_bank_transaction_table(db)

    sales_rows = db.execute(
        text(
            f"""
            SELECT id, request_no, request_date, customer_id, customer_name,
                   currency, total_amount, posted_at
            FROM {LEDGER_TABLE}
            WHERE customer_id = :customer_id
              AND status = 'ACTIVE'
              AND request_date > :previous_request_cutoff
              AND request_date <= :current_request_cutoff
            ORDER BY request_date, request_no
            """
        ),
        {
            "customer_id": customer_id,
            "previous_request_cutoff": previous_request_cutoff,
            "current_request_cutoff": current_request_cutoff,
        },
    ).all()

    bank_columns = {
        row[1]
        for row in db.execute(text(f"PRAGMA table_info({BANK_TABLE})")).all()
    }
    if "matched_customer_id" not in bank_columns:
        db.execute(
            text(
                f"ALTER TABLE {BANK_TABLE} "
                "ADD COLUMN matched_customer_id VARCHAR(128) NOT NULL DEFAULT ''"
            )
        )
    if "customer_match_status" not in bank_columns:
        db.execute(
            text(
                f"ALTER TABLE {BANK_TABLE} "
                "ADD COLUMN customer_match_status VARCHAR(32) NOT NULL DEFAULT ''"
            )
        )
    db.commit()

    payment_rows = db.execute(
        text(
            f"""
            SELECT id, bank_code, bank_name, account_number, transaction_id,
                   transaction_date, amount, counterparty, description, balance
            FROM {BANK_TABLE}
            WHERE direction = 'CREDIT'
              AND matched_customer_id = :customer_id
              AND customer_match_status = 'MATCHED'
              AND transaction_date > :previous_bank_cutoff
              AND transaction_date <= :current_bank_cutoff
            ORDER BY transaction_date, transaction_id
            """
        ),
        {
            "customer_id": customer_id,
            "previous_bank_cutoff": previous_bank_cutoff,
            "current_bank_cutoff": current_bank_cutoff,
        },
    ).all()

    sales = [dict(row._mapping) for row in sales_rows]
    payments = [dict(row._mapping) for row in payment_rows]

    sales_total = sum((_decimal(row["total_amount"]) for row in sales), Decimal("0"))
    payment_total = sum((_decimal(row["amount"]) for row in payments), Decimal("0"))
    period_outstanding = sales_total - payment_total

    if sales_total == 0 and payment_total == 0:
        status = "NO_ACTIVITY"
    elif sales_total == 0 and payment_total > 0:
        status = "NO_SALES"
    elif period_outstanding == 0:
        status = "SETTLED"
    elif payment_total == 0 and sales_total > 0:
        status = "UNPAID"
    elif period_outstanding > 0:
        status = "PARTIAL"
    else:
        status = "OVERPAID"

    customer_name = ""
    if sales:
        customer_name = str(sales[0].get("customer_name", "") or "")

    return {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "period": {
            "previous_request_cutoff": previous_request_cutoff,
            "current_request_cutoff": current_request_cutoff,
            "previous_bank_cutoff": previous_bank_cutoff,
            "current_bank_cutoff": current_bank_cutoff,
            "request_rule": "previous_request_cutoff < request_date <= current_request_cutoff",
            "bank_rule": "previous_bank_cutoff < transaction_date <= current_bank_cutoff",
        },
        "sales_count": len(sales),
        "sales_total": _money(sales_total),
        "payment_count": len(payments),
        "payment_total": _money(payment_total),
        "period_outstanding": _money(period_outstanding),
        "status": status,
        "sales": sales,
        "payments": payments,
    }

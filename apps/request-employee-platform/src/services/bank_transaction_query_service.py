from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.multi_bank_csv_import_service import (
    BANK_TABLE,
    ensure_bank_transaction_table,
)


def list_bank_transactions(
    db: Session,
    *,
    bank_code: str = "",
    account_number: str = "",
    direction: str = "",
    transaction_date_from: str = "",
    transaction_date_to: str = "",
    counterparty: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    ensure_bank_transaction_table(db)

    clauses = []
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 1000)}

    if bank_code:
        clauses.append("bank_code = :bank_code")
        params["bank_code"] = bank_code
    if account_number:
        clauses.append("account_number LIKE :account_number")
        params["account_number"] = f"%{account_number}%"
    if direction:
        clauses.append("direction = :direction")
        params["direction"] = direction
    if transaction_date_from:
        clauses.append("transaction_date >= :date_from")
        params["date_from"] = transaction_date_from
    if transaction_date_to:
        clauses.append("transaction_date <= :date_to")
        params["date_to"] = transaction_date_to
    if counterparty:
        clauses.append("counterparty LIKE :counterparty")
        params["counterparty"] = f"%{counterparty}%"

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(
        text(
            f"""
            SELECT * FROM {BANK_TABLE}
            {where}
            ORDER BY transaction_date DESC, imported_at DESC
            LIMIT :limit
            """
        ),
        params,
    ).all()

    return [dict(row._mapping) for row in rows]


def summarize_bank_transactions(
    db: Session,
    *,
    bank_code: str = "",
    transaction_date_from: str = "",
    transaction_date_to: str = "",
) -> dict[str, Any]:
    ensure_bank_transaction_table(db)

    clauses = []
    params: dict[str, Any] = {}

    if bank_code:
        clauses.append("bank_code = :bank_code")
        params["bank_code"] = bank_code
    if transaction_date_from:
        clauses.append("transaction_date >= :date_from")
        params["date_from"] = transaction_date_from
    if transaction_date_to:
        clauses.append("transaction_date <= :date_to")
        params["date_to"] = transaction_date_to

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(
        text(
            f"""
            SELECT direction, amount
            FROM {BANK_TABLE}
            {where}
            """
        ),
        params,
    ).all()

    credit_count = debit_count = 0
    credit_total = debit_total = 0
    for row in rows:
        direction = row._mapping["direction"]
        try:
            amount = int(float(row._mapping["amount"] or 0))
        except (TypeError, ValueError):
            amount = 0
        if direction == "CREDIT":
            credit_count += 1
            credit_total += amount
        elif direction == "DEBIT":
            debit_count += 1
            debit_total += amount

    return {
        "transaction_count": len(rows),
        "credit_count": credit_count,
        "credit_total": str(credit_total),
        "debit_count": debit_count,
        "debit_total": str(debit_total),
    }


from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_batch_service import ensure_batch_tables


BATCH_TABLE = "tlc_batch"
IMPORT_JOB_TABLE = "tlc_import_job"

BUSINESS_STAGE_TABLES = {
    "compare": "tlc_batch_compare_result",
    "review": "tlc_batch_review_link",
    "sales_ledger": "tlc_batch_sales_ledger_link",
    "bank": "tlc_batch_bank_import_link",
    "reconciliation": "tlc_batch_reconciliation_link",
}


def _table_exists(db: Session, table_name: str) -> bool:
    return db.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name=:table_name"
        ),
        {"table_name": table_name},
    ).first() is not None


def _count(
    db: Session,
    table_name: str,
    *,
    batch_id: str = "",
    extra_where: str = "",
) -> int:
    if not _table_exists(db, table_name):
        return 0

    clauses = []
    params: dict[str, Any] = {}

    if batch_id:
        clauses.append("batch_id=:batch_id")
        params["batch_id"] = batch_id

    if extra_where:
        clauses.append(extra_where)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    value = db.execute(
        text(f"SELECT COUNT(*) FROM {table_name} {where}"),
        params,
    ).scalar()
    return int(value or 0)


def _sum(
    db: Session,
    table_name: str,
    column_name: str,
    *,
    batch_id: str = "",
) -> int:
    if not _table_exists(db, table_name):
        return 0
    where = "WHERE batch_id=:batch_id" if batch_id else ""
    params = {"batch_id": batch_id} if batch_id else {}
    value = db.execute(
        text(
            f"SELECT COALESCE(SUM({column_name}),0) "
            f"FROM {table_name} {where}"
        ),
        params,
    ).scalar()
    return int(value or 0)


def _batch_rows(db: Session, business_month: str) -> list[dict[str, Any]]:
    ensure_batch_tables(db)

    rows = db.execute(
        text(
            f"SELECT * FROM {BATCH_TABLE} "
            "WHERE business_month=:business_month "
            "ORDER BY created_at"
        ),
        {"business_month": business_month},
    ).all()
    return [dict(row._mapping) for row in rows]


def monthly_close_overview(
    db: Session,
    business_month: str,
) -> dict[str, Any]:
    business_month = str(business_month or "").strip()
    if not business_month:
        raise ValueError("business_month is required")

    batches = _batch_rows(db, business_month)

    batch_summaries = []
    blockers = []

    for batch in batches:
        batch_id = batch["id"]

        import_jobs = _count(db, IMPORT_JOB_TABLE, batch_id=batch_id)
        import_errors = _count(
            db,
            IMPORT_JOB_TABLE,
            batch_id=batch_id,
            extra_where="status='ERROR'",
        )
        open_compare_errors = _count(
            db,
            "tlc_batch_compare_error",
            batch_id=batch_id,
            extra_where="status='OPEN'",
        )
        open_import_errors = _count(
            db,
            "tlc_import_job_error",
            batch_id=batch_id,
            extra_where="status='OPEN'",
        )

        stages = {
            name: _count(db, table_name, batch_id=batch_id)
            for name, table_name in BUSINESS_STAGE_TABLES.items()
        }

        completed = batch["status"] == "FINISHED"
        batch_blockers = []

        if import_errors:
            batch_blockers.append(f"import jobs in ERROR={import_errors}")
        if open_compare_errors:
            batch_blockers.append(
                f"open compare errors={open_compare_errors}"
            )
        if open_import_errors:
            batch_blockers.append(
                f"open import errors={open_import_errors}"
            )
        if batch["status"] != "FINISHED":
            batch_blockers.append(f"batch status={batch['status']}")

        if batch_blockers:
            blockers.append(
                {
                    "batch_id": batch_id,
                    "batch_no": batch.get("batch_no", ""),
                    "title": batch.get("title", ""),
                    "items": batch_blockers,
                }
            )

        batch_summaries.append(
            {
                "batch": batch,
                "import_job_count": import_jobs,
                "import_error_job_count": import_errors,
                "open_compare_error_count": open_compare_errors,
                "open_import_error_count": open_import_errors,
                "compare_count": stages["compare"],
                "review_count": stages["review"],
                "sales_ledger_count": stages["sales_ledger"],
                "bank_count": stages["bank"],
                "reconciliation_count": stages["reconciliation"],
                "completed": completed,
                "blockers": batch_blockers,
            }
        )

    total_batches = len(batches)
    finished_batches = sum(
        1 for item in batch_summaries if item["completed"]
    )

    overview = {
        "business_month": business_month,
        "batch_count": total_batches,
        "finished_batch_count": finished_batches,
        "unfinished_batch_count": total_batches - finished_batches,
        "close_ready": total_batches > 0 and not blockers,
        "import_job_count": _sum(
            db,
            IMPORT_JOB_TABLE,
            "record_count",
        ),
        "import_success_record_count": _sum(
            db,
            IMPORT_JOB_TABLE,
            "success_count",
        ),
        "import_error_record_count": _sum(
            db,
            IMPORT_JOB_TABLE,
            "error_count",
        ),
        "batch_summaries": batch_summaries,
        "blockers": blockers,
    }

    if total_batches == 0:
        overview["close_ready"] = False
        overview["blockers"] = [
            {
                "batch_id": "",
                "batch_no": "",
                "title": "",
                "items": ["No batch exists for this business month"],
            }
        ]

    return overview


from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


RUN_TABLE = "tlc_business_test_replay_run"

RESET_TABLES = [
    "tlc_monthly_close_audit",
    "tlc_monthly_close_authorization",
    "tlc_monthly_close_carry_forward",
    "tlc_monthly_close_signoff",
    "tlc_monthly_close_checklist",
    "tlc_import_job_retry",
    "tlc_import_job_error",
    "tlc_purchase_request_stage",
    "tlc_bank_document_stage",
    "tlc_bank_csv_import_job_link",
    "tlc_batch_reconciliation_link",
    "tlc_batch_bank_import_link",
    "tlc_batch_sales_ledger_link",
    "tlc_batch_review_link",
    "tlc_batch_compare_error",
    "tlc_batch_compare_result",
    "tlc_import_job_event",
    "tlc_import_job",
    "tlc_batch_event",
    "tlc_batch",
]


def _table_exists(db: Session, table_name: str) -> bool:
    row = db.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name=:table_name"
        ),
        {"table_name": table_name},
    ).first()
    return row is not None


def ensure_table(db: Session) -> None:
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {RUN_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            business_month VARCHAR(32) NOT NULL,
            action VARCHAR(64) NOT NULL,
            status VARCHAR(64) NOT NULL,
            operator VARCHAR(255) NOT NULL,
            requested_at VARCHAR(64) NOT NULL,
            completed_at VARCHAR(64) NOT NULL DEFAULT '',
            deleted_count INTEGER NOT NULL DEFAULT 0,
            created_count INTEGER NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT ''
        )
    """))
    db.commit()


def _record_run(
    db: Session,
    *,
    business_month: str,
    action: str,
    status: str,
    operator: str,
    deleted_count: int = 0,
    created_count: int = 0,
    message: str = "",
) -> dict[str, Any]:
    ensure_table(db)
    now = datetime.now(timezone.utc).isoformat()
    run_id = uuid4().hex
    db.execute(text(f"""
        INSERT INTO {RUN_TABLE} (
            id, business_month, action, status,
            operator, requested_at, completed_at,
            deleted_count, created_count, message
        ) VALUES (
            :id, :business_month, :action, :status,
            :operator, :requested_at, :completed_at,
            :deleted_count, :created_count, :message
        )
    """), {
        "id": run_id,
        "business_month": business_month,
        "action": action,
        "status": status,
        "operator": operator,
        "requested_at": now,
        "completed_at": now,
        "deleted_count": deleted_count,
        "created_count": created_count,
        "message": message,
    })
    db.commit()
    row = db.execute(
        text(f"SELECT * FROM {RUN_TABLE} WHERE id=:id"),
        {"id": run_id},
    ).first()
    return dict(row._mapping)


def reset_business_month(
    db: Session,
    *,
    business_month: str,
    operator: str,
    confirmation: str,
) -> dict[str, Any]:
    ensure_table(db)

    business_month = str(business_month or "").strip()
    operator = str(operator or "").strip()
    confirmation = str(confirmation or "").strip()

    if not business_month:
        raise ValueError("business_month is required")
    if not operator:
        raise ValueError("operator is required")
    if confirmation != f"RESET {business_month}":
        raise ValueError(
            f"confirmation must exactly equal: RESET {business_month}"
        )

    batch_ids: list[str] = []
    if _table_exists(db, "tlc_batch"):
        batch_ids = [
            str(row[0])
            for row in db.execute(
                text(
                    "SELECT id FROM tlc_batch "
                    "WHERE business_month=:business_month"
                ),
                {"business_month": business_month},
            ).all()
        ]

    deleted_total = 0

    for table_name in RESET_TABLES:
        if not _table_exists(db, table_name):
            continue

        if table_name in {
            "tlc_monthly_close_audit",
            "tlc_monthly_close_authorization",
            "tlc_monthly_close_signoff",
            "tlc_monthly_close_checklist",
        }:
            result = db.execute(
                text(
                    f"DELETE FROM {table_name} "
                    "WHERE business_month=:business_month"
                ),
                {"business_month": business_month},
            )
            deleted_total += int(result.rowcount or 0)
            continue

        if table_name == "tlc_monthly_close_carry_forward":
            result = db.execute(
                text(
                    f"DELETE FROM {table_name} "
                    "WHERE source_month=:business_month "
                    "OR target_month=:business_month"
                ),
                {"business_month": business_month},
            )
            deleted_total += int(result.rowcount or 0)
            continue

        if table_name == "tlc_batch":
            result = db.execute(
                text(
                    "DELETE FROM tlc_batch "
                    "WHERE business_month=:business_month"
                ),
                {"business_month": business_month},
            )
            deleted_total += int(result.rowcount or 0)
            continue

        columns = {
            str(row[1])
            for row in db.execute(
                text(f"PRAGMA table_info({table_name})")
            ).all()
        }

        if "batch_id" in columns and batch_ids:
            placeholders = ",".join(
                f":batch_id_{index}"
                for index, _ in enumerate(batch_ids)
            )
            params = {
                f"batch_id_{index}": value
                for index, value in enumerate(batch_ids)
            }
            result = db.execute(
                text(
                    f"DELETE FROM {table_name} "
                    f"WHERE batch_id IN ({placeholders})"
                ),
                params,
            )
            deleted_total += int(result.rowcount or 0)
            continue

        if "import_job_id" in columns and batch_ids and _table_exists(
            db, "tlc_import_job"
        ):
            placeholders = ",".join(
                f":batch_id_{index}"
                for index, _ in enumerate(batch_ids)
            )
            params = {
                f"batch_id_{index}": value
                for index, value in enumerate(batch_ids)
            }
            result = db.execute(
                text(
                    f"DELETE FROM {table_name} "
                    "WHERE import_job_id IN ("
                    "SELECT id FROM tlc_import_job "
                    f"WHERE batch_id IN ({placeholders})"
                    ")"
                ),
                params,
            )
            deleted_total += int(result.rowcount or 0)

    db.commit()

    run = _record_run(
        db,
        business_month=business_month,
        action="RESET",
        status="SUCCESS",
        operator=operator,
        deleted_count=deleted_total,
        message="Business-month test data reset completed",
    )

    return {
        "business_month": business_month,
        "deleted_count": deleted_total,
        "run": run,
    }


def create_replay_scenario(
    db: Session,
    *,
    business_month: str,
    operator: str,
    scenario_name: str = "STANDARD",
) -> dict[str, Any]:
    ensure_table(db)

    business_month = str(business_month or "").strip()
    operator = str(operator or "").strip()
    scenario_name = str(scenario_name or "STANDARD").strip().upper()

    if not business_month:
        raise ValueError("business_month is required")
    if not operator:
        raise ValueError("operator is required")
    if not _table_exists(db, "tlc_batch"):
        raise ValueError("tlc_batch table does not exist")

    existing = db.execute(
        text(
            "SELECT COUNT(*) FROM tlc_batch "
            "WHERE business_month=:business_month"
        ),
        {"business_month": business_month},
    ).scalar()

    if int(existing or 0) > 0:
        raise ValueError(
            "Business month already contains data; reset it before replay"
        )

    batch_id = uuid4().hex
    batch_no = f"REPLAY-{business_month}-{uuid4().hex[:6].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    columns = {
        str(row[1])
        for row in db.execute(text("PRAGMA table_info(tlc_batch)")).all()
    }

    next_sequence_no = 1
    if "sequence_no" in columns:
        next_sequence_no = int(
            db.execute(
                text(
                    "SELECT COALESCE(MAX(sequence_no), 0) + 1 "
                    "FROM tlc_batch"
                )
            ).scalar()
            or 1
        )

    values: dict[str, Any] = {
        "id": batch_id,
        "sequence_no": next_sequence_no,
        "business_month": business_month,
        "batch_no": batch_no,
        "title": f"{scenario_name} Replay {business_month}",
        "status": "NEW",
        "created_by": operator,
        "created_at": now,
        "updated_at": now,
    }
    usable = {
        key: value
        for key, value in values.items()
        if key in columns
    }

    table_info = db.execute(text("PRAGMA table_info(tlc_batch)")).all()
    for column in table_info:
        name = str(column[1])
        not_null = int(column[3] or 0) == 1
        default_value = column[4]
        primary_key = int(column[5] or 0) == 1
        if (
            name not in usable
            and not_null
            and default_value is None
            and not primary_key
        ):
            if name.endswith("_no") or name.endswith("_count"):
                usable[name] = 0
            elif name.endswith("_at"):
                usable[name] = now
            else:
                usable[name] = ""

    db.execute(
        text(
            f"INSERT INTO tlc_batch "
            f"({','.join(usable.keys())}) "
            f"VALUES ({','.join(':'+key for key in usable)})"
        ),
        usable,
    )

    created_count = 1

    if _table_exists(db, "tlc_import_job"):
        job_columns = {
            str(row[1])
            for row in db.execute(
                text("PRAGMA table_info(tlc_import_job)")
            ).all()
        }
        import_types = ["REQUEST_EXCEL", "BANK_CSV"]
        for import_type in import_types:
            job_values = {
                "id": uuid4().hex,
                "batch_id": batch_id,
                "import_type": import_type,
                "source_name": f"{import_type.lower()}_replay.dat",
                "source_reference": (
                    f"replay:{business_month}:{import_type}:"
                    f"{uuid4().hex}"
                ),
                "status": "NEW",
                "record_count": 0,
                "success_count": 0,
                "error_count": 0,
                "duplicate_count": 0,
                "message": "Replay seed",
                "created_by": operator,
                "created_at": now,
                "updated_at": now,
            }
            usable_job = {
                key: value
                for key, value in job_values.items()
                if key in job_columns
            }
            db.execute(
                text(
                    f"INSERT INTO tlc_import_job "
                    f"({','.join(usable_job.keys())}) "
                    f"VALUES ({','.join(':'+key for key in usable_job)})"
                ),
                usable_job,
            )
            created_count += 1

    db.commit()

    run = _record_run(
        db,
        business_month=business_month,
        action="REPLAY",
        status="SUCCESS",
        operator=operator,
        created_count=created_count,
        message=f"Scenario {scenario_name} replay created",
    )

    return {
        "business_month": business_month,
        "scenario_name": scenario_name,
        "batch_id": batch_id,
        "batch_no": batch_no,
        "created_count": created_count,
        "run": run,
    }


def list_runs(
    db: Session,
    *,
    business_month: str = "",
    limit: int = 200,
) -> list[dict[str, Any]]:
    ensure_table(db)
    params: dict[str, Any] = {
        "limit": min(max(int(limit), 1), 1000)
    }
    where = ""
    if business_month:
        where = "WHERE business_month=:business_month"
        params["business_month"] = business_month

    rows = db.execute(
        text(
            f"SELECT * FROM {RUN_TABLE} "
            f"{where} ORDER BY requested_at DESC LIMIT :limit"
        ),
        params,
    ).all()
    return [dict(row._mapping) for row in rows]

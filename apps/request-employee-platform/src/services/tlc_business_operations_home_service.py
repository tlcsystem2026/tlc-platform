
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_batch_service import ensure_batch_tables


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
    where: str = "",
    params: dict[str, Any] | None = None,
) -> int:
    if not _table_exists(db, table_name):
        return 0
    value = db.execute(
        text(f"SELECT COUNT(*) FROM {table_name} {where}"),
        params or {},
    ).scalar()
    return int(value or 0)


def _latest_month(db: Session) -> str:
    row = db.execute(
        text(
            "SELECT business_month FROM tlc_batch "
            "WHERE COALESCE(business_month,'')<>'' "
            "ORDER BY business_month DESC LIMIT 1"
        )
    ).first()
    return str(row[0] or "") if row else ""


def business_operations_home(
    db: Session,
    business_month: str = "",
) -> dict[str, Any]:
    ensure_batch_tables(db)

    business_month = str(business_month or "").strip() or _latest_month(db)

    batch_where = ""
    batch_params: dict[str, Any] = {}
    if business_month:
        batch_where = "WHERE business_month=:business_month"
        batch_params["business_month"] = business_month

    batch_count = _count(db, "tlc_batch", batch_where, batch_params)
    finished_batch_count = _count(
        db,
        "tlc_batch",
        (
            "WHERE business_month=:business_month AND status='FINISHED'"
            if business_month
            else "WHERE status='FINISHED'"
        ),
        batch_params,
    )

    import_job_count = 0
    import_error_job_count = 0
    if _table_exists(db, "tlc_import_job"):
        if business_month:
            import_job_count = int(
                db.execute(
                    text(
                        "SELECT COUNT(*) FROM tlc_import_job j "
                        "JOIN tlc_batch b ON b.id=j.batch_id "
                        "WHERE b.business_month=:business_month"
                    ),
                    batch_params,
                ).scalar()
                or 0
            )
            import_error_job_count = int(
                db.execute(
                    text(
                        "SELECT COUNT(*) FROM tlc_import_job j "
                        "JOIN tlc_batch b ON b.id=j.batch_id "
                        "WHERE b.business_month=:business_month "
                        "AND j.status='ERROR'"
                    ),
                    batch_params,
                ).scalar()
                or 0
            )
        else:
            import_job_count = _count(db, "tlc_import_job")
            import_error_job_count = _count(
                db,
                "tlc_import_job",
                "WHERE status='ERROR'",
            )

    open_import_error_count = 0
    if _table_exists(db, "tlc_import_job_error"):
        if business_month:
            open_import_error_count = int(
                db.execute(
                    text(
                        "SELECT COUNT(*) FROM tlc_import_job_error e "
                        "JOIN tlc_batch b ON b.id=e.batch_id "
                        "WHERE b.business_month=:business_month "
                        "AND e.status='OPEN'"
                    ),
                    batch_params,
                ).scalar()
                or 0
            )
        else:
            open_import_error_count = _count(
                db,
                "tlc_import_job_error",
                "WHERE status='OPEN'",
            )

    pending_authorization_count = 0
    if _table_exists(db, "tlc_monthly_close_authorization"):
        where = "WHERE decision='PENDING'"
        params: dict[str, Any] = {}
        if business_month:
            where += " AND business_month=:business_month"
            params["business_month"] = business_month
        pending_authorization_count = _count(
            db,
            "tlc_monthly_close_authorization",
            where,
            params,
        )

    carry_forward_open_count = 0
    if _table_exists(db, "tlc_monthly_close_carry_forward"):
        where = "WHERE status IN ('OPEN','CONFIRMED')"
        params = {}
        if business_month:
            where += (
                " AND (source_month=:business_month "
                "OR target_month=:business_month)"
            )
            params["business_month"] = business_month
        carry_forward_open_count = _count(
            db,
            "tlc_monthly_close_carry_forward",
            where,
            params,
        )

    signoff_status = ""
    if business_month and _table_exists(db, "tlc_monthly_close_signoff"):
        row = db.execute(
            text(
                "SELECT status FROM tlc_monthly_close_signoff "
                "WHERE business_month=:business_month"
            ),
            {"business_month": business_month},
        ).first()
        signoff_status = str(row[0] or "") if row else ""

    alerts = []
    if import_error_job_count:
        alerts.append(
            {
                "severity": "HIGH",
                "code": "IMPORT_JOB_ERROR",
                "message": f"{import_error_job_count} import jobs are in ERROR",
                "target": "/operational-exception-dashboard",
            }
        )
    if open_import_error_count:
        alerts.append(
            {
                "severity": "HIGH",
                "code": "OPEN_IMPORT_ERROR",
                "message": f"{open_import_error_count} import errors are still OPEN",
                "target": "/import-center",
            }
        )
    if pending_authorization_count:
        alerts.append(
            {
                "severity": "MEDIUM",
                "code": "PENDING_AUTHORIZATION",
                "message": f"{pending_authorization_count} close/reopen authorizations are pending",
                "target": "/monthly-close-center",
            }
        )
    if carry_forward_open_count:
        alerts.append(
            {
                "severity": "MEDIUM",
                "code": "OPEN_CARRY_FORWARD",
                "message": f"{carry_forward_open_count} carry-forward items are unresolved",
                "target": "/monthly-close-center",
            }
        )
    unfinished = max(batch_count - finished_batch_count, 0)
    if unfinished:
        alerts.append(
            {
                "severity": "LOW",
                "code": "BATCH_NOT_FINISHED",
                "message": f"{unfinished} batches are not FINISHED",
                "target": "/batch-center",
            }
        )

    return {
        "business_month": business_month,
        "batch_count": batch_count,
        "finished_batch_count": finished_batch_count,
        "unfinished_batch_count": unfinished,
        "import_job_count": import_job_count,
        "import_error_job_count": import_error_job_count,
        "open_import_error_count": open_import_error_count,
        "pending_authorization_count": pending_authorization_count,
        "carry_forward_open_count": carry_forward_open_count,
        "monthly_close_signoff_status": signoff_status,
        "alert_count": len(alerts),
        "alerts": alerts,
        "navigation": [
            {"name": "Batch Center", "path": "/batch-center"},
            {"name": "Import Center", "path": "/import-center"},
            {"name": "Monthly Close Center", "path": "/monthly-close-center"},
            {
                "name": "Operational Exception Dashboard",
                "path": "/operational-exception-dashboard",
            },
            {
                "name": "Customer Reconciliation Workbench",
                "path": "/customer-reconciliation-workbench",
            },
        ],
    }

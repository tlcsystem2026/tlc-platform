
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_business_operations_home_service import (
    business_operations_home,
)


STEPS = [
    {
        "code": "BATCH_SETUP",
        "name": "建立并确认 Batch",
        "path": "/batch-center",
        "description": "建立本月 Batch，并确认业务年月、范围与负责人。",
    },
    {
        "code": "REQUEST_IMPORT",
        "name": "导入请求书",
        "path": "/import-center",
        "description": "导入请求书 Excel/PDF，并确认导入任务无错误。",
    },
    {
        "code": "COMPARE_REVIEW",
        "name": "比较与审核",
        "path": "/batch-center",
        "description": "完成请求书比较、错误处理与审核确认。",
    },
    {
        "code": "SALES_LEDGER",
        "name": "进入正式销售台账",
        "path": "/batch-center",
        "description": "将审核完成的数据登记到正式销售台账。",
    },
    {
        "code": "BANK_IMPORT",
        "name": "导入银行流水",
        "path": "/import-center",
        "description": "完成银行 CSV/Excel/PDF 的导入或暂存。",
    },
    {
        "code": "RECONCILIATION",
        "name": "客户对账",
        "path": "/customer-reconciliation-workbench",
        "description": "核对销售总额、入金总额与未付金额。",
    },
    {
        "code": "MONTHLY_CLOSE",
        "name": "月结检查与签核",
        "path": "/monthly-close-center",
        "description": "处理阻塞、完成检查清单并执行月结授权。",
    },
]


def _table_exists(db: Session, table_name: str) -> bool:
    return db.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name=:table_name"
        ),
        {"table_name": table_name},
    ).first() is not None


def _count(db: Session, sql: str, params: dict[str, Any]) -> int:
    return int(db.execute(text(sql), params).scalar() or 0)


def guided_monthly_workflow(
    db: Session,
    *,
    business_month: str = "",
) -> dict[str, Any]:
    home = business_operations_home(db, business_month=business_month)
    month = home["business_month"]
    params = {"business_month": month}

    batch_count = home["batch_count"]
    unfinished_batch_count = home["unfinished_batch_count"]
    import_error_job_count = home["import_error_job_count"]
    open_import_error_count = home["open_import_error_count"]

    compare_count = 0
    review_count = 0
    sales_ledger_count = 0
    bank_count = 0
    reconciliation_count = 0

    if month and _table_exists(db, "tlc_batch_compare_result"):
        compare_count = _count(
            db,
            """
            SELECT COUNT(*)
            FROM tlc_batch_compare_result r
            JOIN tlc_batch b ON b.id=r.batch_id
            WHERE b.business_month=:business_month
            """,
            params,
        )

    if month and _table_exists(db, "tlc_batch_review_link"):
        review_count = _count(
            db,
            """
            SELECT COUNT(*)
            FROM tlc_batch_review_link r
            JOIN tlc_batch b ON b.id=r.batch_id
            WHERE b.business_month=:business_month
            """,
            params,
        )

    if month and _table_exists(db, "tlc_batch_sales_ledger_link"):
        sales_ledger_count = _count(
            db,
            """
            SELECT COUNT(*)
            FROM tlc_batch_sales_ledger_link r
            JOIN tlc_batch b ON b.id=r.batch_id
            WHERE b.business_month=:business_month
            """,
            params,
        )

    if month and _table_exists(db, "tlc_batch_bank_import_link"):
        bank_count = _count(
            db,
            """
            SELECT COUNT(*)
            FROM tlc_batch_bank_import_link r
            JOIN tlc_batch b ON b.id=r.batch_id
            WHERE b.business_month=:business_month
            """,
            params,
        )

    if month and _table_exists(db, "tlc_batch_reconciliation_link"):
        reconciliation_count = _count(
            db,
            """
            SELECT COUNT(*)
            FROM tlc_batch_reconciliation_link r
            JOIN tlc_batch b ON b.id=r.batch_id
            WHERE b.business_month=:business_month
            """,
            params,
        )

    signoff_status = home["monthly_close_signoff_status"]

    state = {
        "BATCH_SETUP": {
            "done": batch_count > 0,
            "detail": f"Batch={batch_count}",
        },
        "REQUEST_IMPORT": {
            "done": (
                home["import_job_count"] > 0
                and import_error_job_count == 0
                and open_import_error_count == 0
            ),
            "detail": (
                f"Import Jobs={home['import_job_count']}, "
                f"Error Jobs={import_error_job_count}, "
                f"Open Errors={open_import_error_count}"
            ),
        },
        "COMPARE_REVIEW": {
            "done": compare_count > 0 and review_count > 0,
            "detail": f"Compare={compare_count}, Review={review_count}",
        },
        "SALES_LEDGER": {
            "done": sales_ledger_count > 0,
            "detail": f"Sales Ledger={sales_ledger_count}",
        },
        "BANK_IMPORT": {
            "done": bank_count > 0,
            "detail": f"Bank Imports={bank_count}",
        },
        "RECONCILIATION": {
            "done": reconciliation_count > 0,
            "detail": f"Reconciliation={reconciliation_count}",
        },
        "MONTHLY_CLOSE": {
            "done": (
                unfinished_batch_count == 0
                and signoff_status == "APPROVED"
            ),
            "detail": (
                f"Unfinished Batch={unfinished_batch_count}, "
                f"Sign-off={signoff_status or 'NOT_INITIALIZED'}"
            ),
        },
    }

    steps = []
    first_pending_code = ""
    for index, base in enumerate(STEPS, start=1):
        item = dict(base)
        item["order"] = index
        item["status"] = "DONE" if state[base["code"]]["done"] else "PENDING"
        item["detail"] = state[base["code"]]["detail"]
        if not first_pending_code and item["status"] == "PENDING":
            first_pending_code = item["code"]
            item["recommended"] = True
        else:
            item["recommended"] = False
        steps.append(item)

    completed_count = sum(1 for item in steps if item["status"] == "DONE")

    return {
        "business_month": month,
        "completed_step_count": completed_count,
        "total_step_count": len(steps),
        "progress_percent": round(completed_count * 100 / len(steps)),
        "next_step_code": first_pending_code,
        "all_complete": completed_count == len(steps),
        "steps": steps,
        "alerts": home["alerts"],
    }


from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_business_operations_home_service import (
    business_operations_home,
)
from src.services.tlc_end_to_end_readiness_service import (
    end_to_end_readiness,
)
from src.services.tlc_guided_monthly_workflow_service import (
    guided_monthly_workflow,
)
from src.services.tlc_operational_exception_dashboard_service import (
    operational_exception_dashboard,
)


RUN_TABLE = "tlc_build035_acceptance_run"

ACCEPTANCE_AREAS = [
    ("BATCH", "Batch 管理"),
    ("IMPORT", "统一导入中心"),
    ("COMPARE_REVIEW", "比较与审核"),
    ("SALES_LEDGER", "正式销售台账"),
    ("BANK", "银行流水"),
    ("RECONCILIATION", "客户对账"),
    ("MONTHLY_CLOSE", "月结控制"),
    ("EXCEPTION", "异常管理"),
    ("OPERATIONS_HOME", "业务运营首页"),
    ("GUIDED_WORKFLOW", "月度业务引导"),
    ("READINESS", "端到端准备度"),
    ("RESET_REPLAY", "测试数据重置与回放"),
]


def ensure_table(db: Session) -> None:
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {RUN_TABLE} (
            id VARCHAR(64) PRIMARY KEY,
            business_month VARCHAR(32) NOT NULL,
            status VARCHAR(64) NOT NULL,
            operator VARCHAR(255) NOT NULL,
            executed_at VARCHAR(64) NOT NULL,
            passed_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            readiness_percent INTEGER NOT NULL DEFAULT 0,
            summary TEXT NOT NULL DEFAULT ''
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


def _route_contracts() -> list[dict[str, Any]]:
    return [
        {"code": "BATCH", "path": "/batch-center"},
        {"code": "IMPORT", "path": "/import-center"},
        {"code": "COMPARE_REVIEW", "path": "/batch-center"},
        {"code": "SALES_LEDGER", "path": "/batch-center"},
        {"code": "BANK", "path": "/import-center"},
        {
            "code": "RECONCILIATION",
            "path": "/customer-reconciliation-workbench",
        },
        {"code": "MONTHLY_CLOSE", "path": "/monthly-close-center"},
        {
            "code": "EXCEPTION",
            "path": "/operational-exception-dashboard",
        },
        {
            "code": "OPERATIONS_HOME",
            "path": "/business-operations-home",
        },
        {
            "code": "GUIDED_WORKFLOW",
            "path": "/guided-monthly-workflow",
        },
        {"code": "READINESS", "path": "/end-to-end-readiness"},
        {"code": "RESET_REPLAY", "path": "/business-test-replay"},
    ]


def integrated_acceptance(
    db: Session,
    *,
    business_month: str = "",
) -> dict[str, Any]:
    ensure_table(db)

    home = business_operations_home(db, business_month=business_month)
    month = home["business_month"]
    workflow = guided_monthly_workflow(db, business_month=month)
    readiness = end_to_end_readiness(db, business_month=month)
    exceptions = operational_exception_dashboard(
        db,
        business_month=month,
        limit=2000,
    )

    required_tables = {
        "BATCH": ["tlc_batch"],
        "IMPORT": ["tlc_import_job"],
        "COMPARE_REVIEW": [
            "tlc_batch_compare_result",
            "tlc_batch_review_link",
        ],
        "SALES_LEDGER": ["tlc_batch_sales_ledger_link"],
        "BANK": ["tlc_batch_bank_import_link"],
        "RECONCILIATION": ["tlc_batch_reconciliation_link"],
        "MONTHLY_CLOSE": ["tlc_monthly_close_signoff"],
        "EXCEPTION": [],
        "OPERATIONS_HOME": [],
        "GUIDED_WORKFLOW": [],
        "READINESS": [],
        "RESET_REPLAY": ["tlc_business_test_replay_run"],
    }

    workflow_by_code = {
        item["code"]: item
        for item in workflow.get("steps", [])
    }

    area_results = []
    route_by_code = {
        item["code"]: item["path"]
        for item in _route_contracts()
    }

    for code, name in ACCEPTANCE_AREAS:
        missing_tables = [
            table_name
            for table_name in required_tables.get(code, [])
            if not _table_exists(db, table_name)
        ]

        status = "PASS"
        detail = "基础结构和入口已就绪"

        if missing_tables:
            status = "FAIL"
            detail = "Missing tables: " + ", ".join(missing_tables)
        elif code in workflow_by_code:
            step = workflow_by_code[code]
            detail = (
                f"Workflow status={step['status']}; "
                f"{step.get('detail', '')}"
            )
        elif code == "EXCEPTION":
            detail = (
                f"Exceptions={exceptions['exception_count']}, "
                f"HIGH={exceptions['high_count']}"
            )
        elif code == "OPERATIONS_HOME":
            detail = (
                f"Batch={home['batch_count']}, Alerts={home['alert_count']}"
            )
        elif code == "READINESS":
            detail = (
                f"Readiness={readiness['status']}, "
                f"{readiness['passed_count']}/{readiness['check_count']}"
            )
        elif code == "RESET_REPLAY":
            detail = "Reset/Replay execution history table is available"

        area_results.append(
            {
                "code": code,
                "name": name,
                "status": status,
                "passed": status == "PASS",
                "detail": detail,
                "path": route_by_code.get(code, ""),
            }
        )

    failed = [item for item in area_results if not item["passed"]]

    return {
        "business_month": month,
        "status": "PASS" if not failed else "FAIL",
        "passed_count": len(area_results) - len(failed),
        "failed_count": len(failed),
        "area_count": len(area_results),
        "acceptance_percent": round(
            (len(area_results) - len(failed)) * 100 / len(area_results)
        ),
        "areas": area_results,
        "failed_areas": failed,
        "business_snapshot": {
            "batch_count": home["batch_count"],
            "unfinished_batch_count": home["unfinished_batch_count"],
            "import_error_job_count": home["import_error_job_count"],
            "open_import_error_count": home["open_import_error_count"],
            "pending_authorization_count": home[
                "pending_authorization_count"
            ],
            "carry_forward_open_count": home[
                "carry_forward_open_count"
            ],
        },
        "workflow": {
            "completed_step_count": workflow["completed_step_count"],
            "total_step_count": workflow["total_step_count"],
            "next_step_code": workflow["next_step_code"],
            "all_complete": workflow["all_complete"],
        },
        "readiness": {
            "status": readiness["status"],
            "ready": readiness["ready"],
            "passed_count": readiness["passed_count"],
            "failed_count": readiness["failed_count"],
            "readiness_percent": readiness["readiness_percent"],
        },
        "exceptions": {
            "exception_count": exceptions["exception_count"],
            "high_count": exceptions["high_count"],
            "medium_count": exceptions["medium_count"],
            "low_count": exceptions["low_count"],
        },
    }


def record_acceptance_run(
    db: Session,
    *,
    business_month: str,
    operator: str,
) -> dict[str, Any]:
    ensure_table(db)

    operator = str(operator or "").strip()
    if not operator:
        raise ValueError("operator is required")

    result = integrated_acceptance(
        db,
        business_month=business_month,
    )
    run_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    db.execute(text(f"""
        INSERT INTO {RUN_TABLE} (
            id, business_month, status, operator,
            executed_at, passed_count, failed_count,
            readiness_percent, summary
        ) VALUES (
            :id, :business_month, :status, :operator,
            :executed_at, :passed_count, :failed_count,
            :readiness_percent, :summary
        )
    """), {
        "id": run_id,
        "business_month": result["business_month"],
        "status": result["status"],
        "operator": operator,
        "executed_at": now,
        "passed_count": result["passed_count"],
        "failed_count": result["failed_count"],
        "readiness_percent": result["readiness"][
            "readiness_percent"
        ],
        "summary": (
            f"Acceptance={result['status']}; "
            f"Areas={result['passed_count']}/{result['area_count']}; "
            f"Readiness={result['readiness']['status']}"
        ),
    })
    db.commit()

    row = db.execute(
        text(f"SELECT * FROM {RUN_TABLE} WHERE id=:id"),
        {"id": run_id},
    ).first()

    return {
        "run": dict(row._mapping),
        "result": result,
    }


def list_acceptance_runs(
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
            f"{where} ORDER BY executed_at DESC LIMIT :limit"
        ),
        params,
    ).all()

    return [dict(row._mapping) for row in rows]

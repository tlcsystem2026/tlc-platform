
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.services.tlc_business_operations_home_service import (
    business_operations_home,
)
from src.services.tlc_guided_monthly_workflow_service import (
    guided_monthly_workflow,
)
from src.services.tlc_monthly_close_control_service import (
    monthly_close_overview,
)
from src.services.tlc_operational_exception_dashboard_service import (
    operational_exception_dashboard,
)


CHECKS = [
    ("BUSINESS_MONTH_EXISTS", "业务年月存在"),
    ("BATCH_EXISTS", "至少存在一个 Batch"),
    ("ALL_BATCHES_FINISHED", "全部 Batch 已完成"),
    ("IMPORTS_CLEAN", "导入任务无错误"),
    ("NO_OPEN_IMPORT_ERRORS", "没有未处理导入错误"),
    ("NO_HIGH_EXCEPTIONS", "没有 HIGH 异常"),
    ("NO_PENDING_AUTHORIZATION", "没有待审批授权"),
    ("NO_OPEN_CARRY_FORWARD", "没有未解决结转"),
    ("WORKFLOW_COMPLETE", "七步业务流程全部完成"),
    ("MONTH_CLOSE_READY", "月结条件满足"),
    ("MONTH_SIGNED_OFF", "月结签核已批准"),
]


def end_to_end_readiness(
    db: Session,
    *,
    business_month: str = "",
) -> dict[str, Any]:
    home = business_operations_home(db, business_month=business_month)
    month = home["business_month"]
    workflow = guided_monthly_workflow(db, business_month=month)
    exceptions = operational_exception_dashboard(
        db,
        business_month=month,
        limit=2000,
    )
    close = monthly_close_overview(db, month) if month else {
        "close_ready": False,
        "batch_count": 0,
        "finished_batch_count": 0,
        "unfinished_batch_count": 0,
        "blockers": [],
    }

    values = {
        "BUSINESS_MONTH_EXISTS": bool(month),
        "BATCH_EXISTS": home["batch_count"] > 0,
        "ALL_BATCHES_FINISHED": (
            home["batch_count"] > 0
            and home["unfinished_batch_count"] == 0
        ),
        "IMPORTS_CLEAN": home["import_error_job_count"] == 0,
        "NO_OPEN_IMPORT_ERRORS": home["open_import_error_count"] == 0,
        "NO_HIGH_EXCEPTIONS": exceptions["high_count"] == 0,
        "NO_PENDING_AUTHORIZATION": home["pending_authorization_count"] == 0,
        "NO_OPEN_CARRY_FORWARD": home["carry_forward_open_count"] == 0,
        "WORKFLOW_COMPLETE": workflow["all_complete"],
        "MONTH_CLOSE_READY": bool(close["close_ready"]),
        "MONTH_SIGNED_OFF": (
            home["monthly_close_signoff_status"] == "APPROVED"
        ),
    }

    detail_map = {
        "BUSINESS_MONTH_EXISTS": month or "No business month",
        "BATCH_EXISTS": f"Batch={home['batch_count']}",
        "ALL_BATCHES_FINISHED": (
            f"Finished={home['finished_batch_count']}, "
            f"Unfinished={home['unfinished_batch_count']}"
        ),
        "IMPORTS_CLEAN": (
            f"Import Error Jobs={home['import_error_job_count']}"
        ),
        "NO_OPEN_IMPORT_ERRORS": (
            f"Open Import Errors={home['open_import_error_count']}"
        ),
        "NO_HIGH_EXCEPTIONS": (
            f"High Exceptions={exceptions['high_count']}"
        ),
        "NO_PENDING_AUTHORIZATION": (
            f"Pending Authorizations={home['pending_authorization_count']}"
        ),
        "NO_OPEN_CARRY_FORWARD": (
            f"Open Carry Forwards={home['carry_forward_open_count']}"
        ),
        "WORKFLOW_COMPLETE": (
            f"Workflow={workflow['completed_step_count']}/"
            f"{workflow['total_step_count']}"
        ),
        "MONTH_CLOSE_READY": (
            f"Close Ready={close['close_ready']}; "
            f"Blockers={len(close.get('blockers', []))}"
        ),
        "MONTH_SIGNED_OFF": (
            f"Sign-off={home['monthly_close_signoff_status'] or 'NOT_INITIALIZED'}"
        ),
    }

    checks = []
    for code, name in CHECKS:
        passed = bool(values[code])
        checks.append(
            {
                "code": code,
                "name": name,
                "passed": passed,
                "status": "PASS" if passed else "FAIL",
                "detail": detail_map[code],
            }
        )

    failed = [item for item in checks if not item["passed"]]

    return {
        "business_month": month,
        "ready": not failed,
        "status": "READY" if not failed else "NOT_READY",
        "check_count": len(checks),
        "passed_count": len(checks) - len(failed),
        "failed_count": len(failed),
        "readiness_percent": round(
            (len(checks) - len(failed)) * 100 / len(checks)
        ),
        "checks": checks,
        "failed_checks": failed,
        "workflow": workflow,
        "exceptions": {
            "exception_count": exceptions["exception_count"],
            "high_count": exceptions["high_count"],
            "medium_count": exceptions["medium_count"],
            "low_count": exceptions["low_count"],
            "by_category": exceptions["by_category"],
        },
        "monthly_close": {
            "close_ready": close["close_ready"],
            "blockers": close.get("blockers", []),
        },
        "recommended_path": (
            "/guided-monthly-workflow"
            if failed
            else "/monthly-close-center"
        ),
    }

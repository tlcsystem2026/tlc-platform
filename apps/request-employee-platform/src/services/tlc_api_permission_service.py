from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from re import fullmatch

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_access_control_service import ensure_schema


@dataclass(frozen=True)
class PermissionRequirement:
    module_code: str
    action_code: str


RULES: tuple[tuple[str, str, str, str], ...] = (
    ("*", r"/api/database-maintenance(?:/.*)?", "DATABASE_MAINTENANCE", "MAINTAIN"),
    ("DELETE", r"/api/legal-entities/[^/]+", "LEGAL_ENTITY_MASTER", "DELETE"),
    ("POST", r"/api/tlc-customers/delete-batch", "CUSTOMER_MASTER", "DELETE"),
    ("DELETE", r"/api/tlc-customers/[^/]+", "CUSTOMER_MASTER", "DELETE"),
    ("POST", r"/api/tlc-(?:banks|bank-accounts)/delete-batch", "BANK_MASTER", "DELETE"),
    ("DELETE", r"/api/tlc-(?:banks|bank-accounts)/[^/]+", "BANK_MASTER", "DELETE"),
    ("POST", r"/api/access-control/(?:departments|users)", "USER_PERMISSION", "MAINTAIN"),
    ("PUT", r"/api/access-control/(?:users/[^/]+/roles|roles/[^/]+/permissions)", "USER_PERMISSION", "MAINTAIN"),
    ("POST", r"/api/requests/pending-review/(?:bulk-resolve|[^/]+/resolve)", "REQUEST_BUSINESS_REVIEW", "APPROVE"),
    ("POST", r"/api/sales-ledger/from-pending-review/[^/]+", "FORMAL_SALES_LEDGER", "APPROVE"),
    ("POST", r"/api/sales-ledger/bulk-void", "FORMAL_SALES_LEDGER", "EDIT"),
    ("POST", r"/api/sales-ledger/admin/cleanup-test-data", "FORMAL_SALES_LEDGER", "DELETE"),
    ("POST", r"/api/tlc-monthly-close/[^/]+/checklist/initialize", "MONTHLY_CLOSE", "EXECUTE"),
    ("PUT", r"/api/tlc-monthly-close/checklist/items/[^/]+", "MONTHLY_CLOSE", "EDIT"),
    ("PUT", r"/api/tlc-monthly-close/[^/]+/signoff", "MONTHLY_CLOSE", "APPROVE"),
    ("POST", r"/api/tlc-monthly-close/authorizations", "MONTHLY_CLOSE", "EXECUTE"),
    ("PUT", r"/api/tlc-monthly-close/authorizations/[^/]+/decision", "MONTHLY_CLOSE", "APPROVE"),
    ("PUT", r"/api/tlc-monthly-close/authorizations/[^/]+/execute", "MONTHLY_CLOSE", "EXECUTE"),
)




# TLC_BUSINESS_PERMISSION_COVERAGE_R1
BUSINESS_RULES: tuple[tuple[str, str, str], ...] = (
    (r"/(?:dashboard)?", "DASHBOARD", "VIEW"),
    (r"/api/dashboard(?:/.*)?", "DASHBOARD", "VIEW"),
    (r"/(?:request-review-center|request-batch-compare-import-center)", "REQUEST_BATCH", "VIEW"),
    (r"/api/(?:tlc-request-batch-compare-import|tlc-batches|tlc-import-jobs)(?:/.*)?", "REQUEST_BATCH", "AUTO"),
    (r"/review", "REQUEST_FILE_REVIEW", "VIEW"),
    (r"/api/(?:request-reviews|tlc-batches/[^/]+/review)(?:/.*)?", "REQUEST_FILE_REVIEW", "AUTO"),
    (r"/requests/review-workbench", "REQUEST_BUSINESS_REVIEW", "VIEW"),
    (r"/api/requests/pending-review(?:/.*)?", "REQUEST_BUSINESS_REVIEW", "AUTO"),
    (r"/sales", "SALES_STATISTICS", "VIEW"),
    (r"/api/sales-ledger/statistics(?:/.*)?", "SALES_STATISTICS", "VIEW"),
    (r"/bank-import", "BANK_IMPORT", "VIEW"),
    (r"/api/(?:multi-bank-import|bank-import|tlc-bank-csv)(?:/.*)?", "BANK_IMPORT", "AUTO"),
    (r"/(?:customer-payment-reconciliation(?:/confirm)?|customer-reconciliation-workbench|customer-reconciliation-confirmation-center)", "CUSTOMER_RECONCILIATION", "VIEW"),
    (r"/api/(?:customer-reconciliation|customer-period-reconciliation|tlc-customer-reconciliation)(?:/.*)?", "CUSTOMER_RECONCILIATION", "AUTO"),
    (r"/operational-exception-dashboard", "OPERATIONAL_EXCEPTION", "VIEW"),
    (r"/api/tlc-operational-exceptions(?:/.*)?", "OPERATIONAL_EXCEPTION", "AUTO"),
    (r"/guided-monthly-workflow", "MONTHLY_WORKFLOW", "VIEW"),
    (r"/api/tlc-guided-monthly-workflow(?:/.*)?", "MONTHLY_WORKFLOW", "AUTO"),
    (r"/monthly-close-center", "MONTHLY_CLOSE", "VIEW"),
)

NAVIGATION_MODULES: dict[str, str] = {
    "/dashboard": "DASHBOARD",
    "/request-review-center": "REQUEST_BATCH",
    "/request-batch-compare-import-center": "REQUEST_BATCH",
    "/review": "REQUEST_FILE_REVIEW",
    "/requests/review-workbench": "REQUEST_BUSINESS_REVIEW",
    "/sales": "SALES_STATISTICS",
    "/bank-import": "BANK_IMPORT",
    "/customer-payment-reconciliation": "CUSTOMER_RECONCILIATION",
    "/customer-reconciliation-workbench": "CUSTOMER_RECONCILIATION",
    "/customer-reconciliation-confirmation-center": "CUSTOMER_RECONCILIATION",
    "/operational-exception-dashboard": "OPERATIONAL_EXCEPTION",
    "/guided-monthly-workflow": "MONTHLY_WORKFLOW",
    "/monthly-close-center": "MONTHLY_CLOSE",
}

def _business_action(method: str, configured: str) -> str:
    if configured != "AUTO":
        return configured
    return {"GET": "VIEW", "HEAD": "VIEW", "OPTIONS": "VIEW", "DELETE": "DELETE"}.get(method, "EDIT")

def visible_modules(db: Session, session: dict) -> dict:
    ensure_schema(db)
    user_id = str(session.get("user_id") or "")
    roles = {str(row[0]) for row in db.execute(text(
        "SELECT role_code FROM tlc_user_role WHERE user_id=:user"
    ), {"user": user_id}).all()}
    if "SUPER_ADMIN" in roles:
        modules = sorted({module for module in NAVIGATION_MODULES.values()})
    else:
        modules = sorted({str(row[0]) for row in db.execute(text("""SELECT DISTINCT rp.module_code
          FROM tlc_role_permission rp JOIN tlc_user_role ur ON ur.role_code=rp.role_code
          WHERE ur.user_id=:user AND rp.action_code='VIEW' AND rp.allowed=1"""), {"user": user_id}).all()})
    return {"modules": modules, "navigation": NAVIGATION_MODULES}

def dashboard_permission_script() -> str:
    return r"""<script data-tlc-contract="TLC_BUSINESS_PERMISSION_COVERAGE_R1">
(async()=>{try{const r=await fetch('/api/auth/navigation',{credentials:'same-origin'});if(!r.ok)return;
const p=await r.json(),allowed=new Set(p.modules||[]),mapping=p.navigation||{};
document.querySelectorAll('a[href]').forEach(a=>{const path=new URL(a.href,location.origin).pathname;
let module='';for(const [prefix,value] of Object.entries(mapping)){if(path===prefix||path.startsWith(prefix+'/')){module=value;break;}}
if(module&&!allowed.has(module)){const card=a.closest('.navitem,.todo,.metric');(card||a).remove();}});
}catch(e){console.error('Permission navigation filter failed',e);}})();</script>"""

def requirement_for(method: str, path: str) -> PermissionRequirement | None:
    method = method.upper()
    normalized = path.rstrip("/") or "/"
    for expected, pattern, module, action in RULES:
        if expected in ("*", method) and fullmatch(pattern, normalized):
            return PermissionRequirement(module, action)
    for pattern, module, configured_action in BUSINESS_RULES:
        if fullmatch(pattern, normalized):
            return PermissionRequirement(module, _business_action(method, configured_action))
    return None


def _ensure_audit(db: Session) -> None:
    db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_api_permission_audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT,user_id VARCHAR(64) NOT NULL DEFAULT '',
      method VARCHAR(16) NOT NULL,path VARCHAR(1000) NOT NULL,module_code VARCHAR(128) NOT NULL,
      action_code VARCHAR(32) NOT NULL,allowed INTEGER NOT NULL,data_scope VARCHAR(32) NOT NULL DEFAULT '',
      detail VARCHAR(1000) NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL)"""))


def authorize(db: Session, session: dict, method: str, path: str) -> dict:
    requirement = requirement_for(method, path)
    if requirement is None:
        return {"required": False, "allowed": True, "data_scope": ""}
    ensure_schema(db)
    _ensure_audit(db)
    user_id = str(session.get("user_id") or "")
    roles = {str(row[0]) for row in db.execute(text(
        "SELECT role_code FROM tlc_user_role WHERE user_id=:user"
    ), {"user": user_id}).all()}
    scope = ""
    allowed = "SUPER_ADMIN" in roles
    if allowed:
        scope = "ALL"
    else:
        row = db.execute(text("""SELECT rp.data_scope FROM tlc_role_permission rp
          JOIN tlc_user_role ur ON ur.role_code=rp.role_code
          WHERE ur.user_id=:user AND rp.module_code=:module AND rp.action_code=:action
            AND rp.allowed=1
          ORDER BY CASE rp.data_scope WHEN 'ALL' THEN 4 WHEN 'LEGAL_ENTITY' THEN 3
            WHEN 'DEPARTMENT' THEN 2 WHEN 'SELF' THEN 1 ELSE 0 END DESC LIMIT 1"""), {
            "user": user_id, "module": requirement.module_code,
            "action": requirement.action_code,
        }).first()
        if row:
            scope = str(row[0])
            allowed = scope == "ALL" or (
                scope == "LEGAL_ENTITY" and bool(session.get("legal_entity_id"))
            ) or (scope == "DEPARTMENT" and bool(session.get("department_id"))) or scope == "SELF"
    detail = "" if allowed else "NO_MATCHING_ROLE_PERMISSION_OR_SCOPE"
    db.execute(text("""INSERT INTO tlc_api_permission_audit(
      user_id,method,path,module_code,action_code,allowed,data_scope,detail,created_at)
      VALUES(:user,:method,:path,:module,:action,:allowed,:scope,:detail,:created)"""), {
        "user": user_id, "method": method.upper(), "path": path,
        "module": requirement.module_code, "action": requirement.action_code,
        "allowed": 1 if allowed else 0, "scope": scope, "detail": detail,
        "created": datetime.now(timezone.utc).isoformat(),
    })
    db.commit()
    return {
        "required": True, "allowed": allowed, "data_scope": scope,
        "module_code": requirement.module_code,
        "action_code": requirement.action_code,
    }

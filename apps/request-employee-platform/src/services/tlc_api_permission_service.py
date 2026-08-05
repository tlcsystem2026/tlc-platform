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


def requirement_for(method: str, path: str) -> PermissionRequirement | None:
    method = method.upper()
    normalized = path.rstrip("/") or "/"
    for expected, pattern, module, action in RULES:
        if expected in ("*", method) and fullmatch(pattern, normalized):
            return PermissionRequirement(module, action)
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

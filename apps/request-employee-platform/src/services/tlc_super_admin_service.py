from __future__ import annotations

import ipaddress
import os
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_access_control_service import ACTIONS, MODULES, audit, ensure_schema, now


DEFAULT_INTERNAL_CIDRS = "127.0.0.1/32,::1/128"


def internal_ip_allowed(client_ip: str) -> bool:
    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    configured = os.getenv("TLC_INTERNAL_ADMIN_CIDRS", DEFAULT_INTERNAL_CIDRS)
    for value in configured.split(","):
        value = value.strip()
        if not value:
            continue
        try:
            if address in ipaddress.ip_network(value, strict=False):
                return True
        except ValueError:
            continue
    return False


def _active_super_admin_ids(db: Session) -> list[str]:
    ensure_schema(db)
    return [
        str(row[0])
        for row in db.execute(
            text(
                """SELECT u.id FROM tlc_user_master u
                JOIN tlc_user_role r ON r.user_id=u.id
                WHERE r.role_code='SUPER_ADMIN' AND u.active=1
                ORDER BY u.employee_no"""
            )
        ).all()
    ]


def _require_reason(reason: str) -> str:
    result = str(reason or "").strip()
    if not result:
        raise ValueError("必须填写设置理由")
    return result


def _require_actor(db: Session, actor_user_id: str, bootstrap: bool = False) -> None:
    if bootstrap:
        return
    if actor_user_id not in _active_super_admin_ids(db):
        raise PermissionError("操作人不是有效的超级管理员")


def _ensure_all_permissions(db: Session) -> None:
    stamp = now()
    for module_code, _ in MODULES:
        for action_code in ACTIONS:
            db.execute(
                text(
                    """INSERT INTO tlc_role_permission
                    (id,role_code,module_code,action_code,data_scope,allowed,updated_at,updated_by)
                    VALUES(:id,'SUPER_ADMIN',:module,:action,'ALL',1,:updated,'SYSTEM')
                    ON CONFLICT(role_code,module_code,action_code) DO UPDATE SET
                    data_scope='ALL',allowed=1,updated_at=:updated,updated_by='SYSTEM'"""
                ),
                {"id": uuid4().hex, "module": module_code, "action": action_code, "updated": stamp},
            )


def overview(db: Session) -> dict:
    ensure_schema(db)
    _ensure_all_permissions(db)
    db.commit()
    users = [dict(row._mapping) for row in db.execute(text("SELECT * FROM tlc_user_master ORDER BY employee_no")).all()]
    assigned = set(_active_super_admin_ids(db))
    admins = [user for user in users if user["id"] in assigned]
    candidates = [user for user in users if user["id"] not in assigned and bool(user["active"])]
    return {
        "super_admins": admins,
        "candidates": candidates,
        "active_count": len(admins),
        "internal_cidrs": os.getenv("TLC_INTERNAL_ADMIN_CIDRS", DEFAULT_INTERNAL_CIDRS),
        "permission_rule": "ALL_MODULES_ALL_ACTIONS_ALL_SCOPE",
    }


def grant(db: Session, target_user_id: str, actor_user_id: str, reason: str, confirmation: str) -> dict:
    ensure_schema(db)
    reason = _require_reason(reason)
    if confirmation != "GRANT_SUPER_ADMIN":
        raise ValueError("确认文字不正确")
    target = db.execute(text("SELECT id,active FROM tlc_user_master WHERE id=:id"), {"id": target_user_id}).first()
    if not target:
        raise ValueError("所选人员不存在")
    if not bool(target._mapping["active"]):
        raise ValueError("停用人员不能设置为超级管理员")
    current = _active_super_admin_ids(db)
    bootstrap = len(current) == 0
    _require_actor(db, actor_user_id, bootstrap=bootstrap)
    _ensure_all_permissions(db)
    db.execute(
        text("INSERT OR IGNORE INTO tlc_user_role(id,user_id,role_code,created_at,created_by) VALUES(:id,:user,'SUPER_ADMIN',:created,:actor)"),
        {"id": uuid4().hex, "user": target_user_id, "created": now(), "actor": actor_user_id or "BOOTSTRAP"},
    )
    audit(db, actor_user_id or "BOOTSTRAP", "SUPER_ADMIN", target_user_id, "GRANT", reason)
    db.commit()
    return {"target_user_id": target_user_id, "granted": True, "bootstrap": bootstrap}


def revoke(db: Session, target_user_id: str, actor_user_id: str, reason: str, confirmation: str) -> dict:
    ensure_schema(db)
    reason = _require_reason(reason)
    if confirmation != "REVOKE_SUPER_ADMIN":
        raise ValueError("确认文字不正确")
    current = _active_super_admin_ids(db)
    _require_actor(db, actor_user_id)
    if target_user_id not in current:
        raise ValueError("所选人员不是有效的超级管理员")
    if len(current) <= 1:
        raise ValueError("至少必须保留一名有效的超级管理员")
    db.execute(text("DELETE FROM tlc_user_role WHERE user_id=:user AND role_code='SUPER_ADMIN'"), {"user": target_user_id})
    audit(db, actor_user_id, "SUPER_ADMIN", target_user_id, "REVOKE", reason)
    db.commit()
    return {"target_user_id": target_user_id, "revoked": True}

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


AUDIT_TABLE = "tlc_database_maintenance_audit"
BACKUP_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
TABLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LOCK = threading.RLock()

TABLE_CATEGORIES = {
    "SYSTEM_MAINTENANCE": "系统维护用表",
    "FUNCTION_MASTER": "功能相关基础数据表",
    "AUDIT_HISTORY": "审计与历史保护表",
    "BUSINESS_MASTER": "业务相关基础数据表",
    "BUSINESS_TRANSACTION": "业务表",
    "UNCLASSIFIED": "未分类表",
}

EXACT_TABLE_CATEGORIES = {
    "customers": "BUSINESS_MASTER",
    "legal_entities": "BUSINESS_MASTER",
    "tlc_customer_master": "BUSINESS_MASTER",
    "tlc_bank_account_profile": "BUSINESS_MASTER",
    "tlc_department_master": "BUSINESS_MASTER",
    "tlc_user_master": "SYSTEM_MAINTENANCE",
    "tlc_role_master": "SYSTEM_MAINTENANCE",
    "tlc_permission_module": "SYSTEM_MAINTENANCE",
    "tlc_user_role": "SYSTEM_MAINTENANCE",
    "tlc_role_permission": "SYSTEM_MAINTENANCE",
    "tlc_permission_audit": "AUDIT_HISTORY",
    "tlc_database_maintenance_audit": "AUDIT_HISTORY",
}


def table_classification(table_name: str) -> dict[str, Any]:
    name = str(table_name or "")
    lower = name.lower()
    category = EXACT_TABLE_CATEGORIES.get(name)
    if not category:
        if lower.endswith("_audit") or "audit" in lower or lower.endswith("_history") or "history" in lower:
            category = "AUDIT_HISTORY"
        elif any(token in lower for token in ("permission", "access_control", "security", "session", "credential", "mfa")):
            category = "SYSTEM_MAINTENANCE"
        elif lower.endswith("_code") or "code_master" in lower or "parameter" in lower or "setting" in lower:
            category = "FUNCTION_MASTER"
        elif lower.endswith("_master") or "customer_master" in lower or "bank_account_profile" in lower:
            category = "BUSINESS_MASTER"
        elif any(token in lower for token in ("request", "sales", "ledger", "bank", "payment", "reconciliation", "monthly", "import", "review", "batch")):
            category = "BUSINESS_TRANSACTION"
        else:
            category = "UNCLASSIFIED"
    policy = {
        "SYSTEM_MAINTENANCE": ("CRITICAL", True, False, False, "仅允许备份；恢复或清除可能影响系统运行或安全"),
        "FUNCTION_MASTER": ("HIGH", True, True, False, "允许备份和受控恢复；禁止整表清除"),
        "AUDIT_HISTORY": ("CRITICAL", True, False, False, "用于审计和安全追溯，只允许备份"),
        "BUSINESS_MASTER": ("HIGH", True, True, True, "允许超级管理员受控维护，执行前必须自动备份"),
        "BUSINESS_TRANSACTION": ("HIGH", True, True, True, "允许超级管理员受控维护，可能影响业务完整性"),
        "UNCLASSIFIED": ("CRITICAL", True, False, False, "尚未明确分类，默认只允许备份"),
    }[category]
    return {"category_code": category, "category_name": TABLE_CATEGORIES[category], "risk_level": policy[0], "can_backup": policy[1], "can_restore": policy[2], "can_clear": policy[3], "maintenance_note": policy[4]}

TABLE_DESCRIPTIONS = {
    "legal_entities": "法人主数据",
    "sales_records": "销售记录",
    "request_compare_runs": "请求书核对执行记录",
    "review_tasks": "审核任务",
    "request_pending_review": "请求书业务审核队列",
    "formal_sales_request_ledger": "正式销售台账",
    "formal_sales_ledger_admin_audit": "正式销售台账管理员审计",
    "tlc_customer_master": "客户主数据",
    "tlc_bank_account_profile": "银行及账户主数据",
    "tlc_request_batch_compare": "请求书批量核对批次",
    "tlc_request_batch_compare_item": "请求书批量核对明细",
    "tlc_request_review_queue": "请求书文件核对队列",
    "tlc_batch_review_link": "批次与文件审核关联",
    "tlc_batch_sales_ledger_link": "批次与销售台账关联",
    "tlc_batch_bank_import_link": "批次与银行流水关联",
    "tlc_batch_reconciliation_link": "批次与客户对账关联",
    "tlc_import_job": "数据导入任务",
    "tlc_import_job_error": "数据导入错误记录",
    "tlc_import_error_retry": "导入错误重试记录",
    "customer_payment_reconciliation_history": "客户销售与入金核对历史",
    "tlc_customer_reconciliation_case": "客户对账案件",
    "tlc_customer_reconciliation_audit": "客户对账操作审计",
    "tlc_customer_auto_match_audit": "客户自动匹配审计",
    "tlc_monthly_close_checklist": "月结检查清单",
    "tlc_monthly_close_signoff": "月结签核记录",
    "tlc_monthly_close_authorization": "月结授权记录",
    "tlc_monthly_close_audit": "月结操作审计",
    "tlc_cross_month_carry_forward": "跨月结转记录",
    "tlc_database_maintenance_audit": "数据库维护操作审计",
}


def table_description(table_name: str) -> str:
    name = str(table_name or "")
    if name in TABLE_DESCRIPTIONS:
        return TABLE_DESCRIPTIONS[name]
    lower = name.lower()
    if lower.endswith("_audit") or "audit" in lower:
        return "系统操作审计记录"
    if lower.endswith("_error") or "error" in lower or "exception" in lower:
        return "系统错误与异常记录"
    if lower.endswith("_history") or "history" in lower:
        return "业务历史记录"
    if lower.endswith("_link") or "_link_" in lower:
        return "业务数据关联记录"
    if lower.endswith("_master") or "master" in lower:
        return "系统基础主数据"
    if "bank" in lower and ("transaction" in lower or "payment" in lower):
        return "银行流水与入金数据"
    if "reconciliation" in lower:
        return "客户对账业务数据"
    if "request" in lower and "review" in lower:
        return "请求书审核业务数据"
    if "request" in lower:
        return "请求书业务数据"
    if "sales" in lower or "ledger" in lower:
        return "销售与台账业务数据"
    if "monthly_close" in lower or "carry_forward" in lower:
        return "月结与结转业务数据"
    return "系统业务数据表（尚未登记详细说明）"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backup_root() -> Path:
    value = os.getenv(
        "TLC_DATABASE_MAINTENANCE_BACKUP_DIR",
        r"C:\TLC-BOS\data\backup\database-maintenance",
    )
    root = Path(value).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _require_sqlite(engine: Engine) -> Path:
    if engine.dialect.name != "sqlite" or not engine.url.database:
        raise RuntimeError("Database maintenance currently supports SQLite only")
    return Path(engine.url.database).resolve()


def _require_super_admin(operator: str, role: str) -> str:
    operator = str(operator or "").strip()
    if str(role or "").strip().upper() != "SUPER_ADMIN":
        raise PermissionError("SUPER_ADMIN role is required")
    allowed = {
        item.strip()
        for item in os.getenv("TLC_SUPER_ADMIN_OPERATORS", "super-admin").split(",")
        if item.strip()
    }
    if operator not in allowed:
        raise PermissionError("Operator is not configured as a SUPER_ADMIN")
    return operator


def _require_reason(reason: str) -> str:
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("Maintenance reason is required")
    return reason


def _quote(value: str) -> str:
    if not TABLE_PATTERN.fullmatch(value):
        raise ValueError("Invalid table name")
    return '"' + value + '"'


def _sqlite_path(path: Path) -> str:
    value = str(path.resolve())
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        return "\\\\?\\" + value
    return value


def _ensure_audit(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text(f"""CREATE TABLE IF NOT EXISTS {AUDIT_TABLE}(
          id VARCHAR(64) PRIMARY KEY,action VARCHAR(64) NOT NULL,
          target_type VARCHAR(32) NOT NULL,target_name VARCHAR(500) NOT NULL DEFAULT '',
          backup_id VARCHAR(64) NOT NULL DEFAULT '',operator VARCHAR(200) NOT NULL,
          reason TEXT NOT NULL DEFAULT '',detail_json TEXT NOT NULL DEFAULT '{{}}',
          created_at VARCHAR(64) NOT NULL)"""))


def _audit(
    engine: Engine,
    action: str,
    target_type: str,
    target_name: str,
    backup_id: str,
    operator: str,
    reason: str,
    detail: dict[str, Any],
) -> None:
    _ensure_audit(engine)
    with engine.begin() as connection:
        connection.execute(text(f"""INSERT INTO {AUDIT_TABLE}(
          id,action,target_type,target_name,backup_id,operator,reason,detail_json,created_at
        ) VALUES(:id,:action,:target_type,:target_name,:backup_id,:operator,:reason,:detail,:created_at)"""),{
            "id": uuid4().hex,
            "action": action,
            "target_type": target_type,
            "target_name": target_name,
            "backup_id": backup_id,
            "operator": operator,
            "reason": reason,
            "detail": json.dumps(detail, ensure_ascii=False),
            "created_at": _now(),
        })


def _sqlite_backup(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(_sqlite_path(source_path))
    destination = sqlite3.connect(_sqlite_path(destination_path))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    with open(_sqlite_path(path), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2))


def _manifest_path(backup_id: str) -> Path:
    if not BACKUP_ID_PATTERN.fullmatch(str(backup_id or "")):
        raise ValueError("Invalid backup_id")
    matches = list(_backup_root().glob(f"*__{backup_id}.json"))
    if len(matches) != 1:
        raise LookupError("Backup not found")
    return matches[0]


def _load_backup(backup_id: str) -> tuple[dict[str, Any], Path]:
    manifest_path = _manifest_path(backup_id)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    database_file = (manifest_path.parent / manifest["file_name"]).resolve()
    if database_file.parent != _backup_root() or not database_file.exists():
        raise LookupError("Backup database file not found")
    return manifest, database_file


def list_tables(engine: Engine) -> list[dict[str, Any]]:
    _ensure_audit(engine)
    result = []
    with engine.connect() as connection:
        for table in sorted(inspect(engine).get_table_names()):
            if table.startswith("sqlite_"):
                continue
            count = int(connection.execute(text(f"SELECT COUNT(*) FROM {_quote(table)}")).scalar_one())
            result.append({
                "table_name": table,
                "table_description": table_description(table),
                "row_count": count,
                **table_classification(table),
                "protected": not table_classification(table)["can_clear"],
            })
    return result


def list_backups() -> list[dict[str, Any]]:
    result = []
    for path in _backup_root().glob("*.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            item["available"] = (path.parent / item["file_name"]).exists()
            result.append(item)
        except (OSError, ValueError, KeyError):
            continue
    return sorted(result, key=lambda item: item.get("created_at", ""), reverse=True)


def list_audit(engine: Engine, limit: int = 200) -> list[dict[str, Any]]:
    _ensure_audit(engine)
    with engine.connect() as connection:
        rows = connection.execute(text(f"""SELECT * FROM {AUDIT_TABLE}
          ORDER BY created_at DESC LIMIT :limit"""), {"limit": min(max(limit, 1), 1000)}).all()
    return [dict(row._mapping) for row in rows]


def create_full_backup(engine: Engine, operator: str, role: str, reason: str, *, action: str = "FULL_BACKUP") -> dict[str, Any]:
    operator = _require_super_admin(operator, role)
    reason = _require_reason(reason)
    source_path = _require_sqlite(engine)
    backup_id = uuid4().hex
    created_at = _now()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"full__{backup_id}.db"
    destination = _backup_root() / file_name
    with LOCK:
        _sqlite_backup(source_path, destination)
        manifest = {
            "backup_id": backup_id,
            "backup_type": "FULL",
            "table_name": "",
            "file_name": file_name,
            "created_at": created_at,
            "operator": operator,
            "reason": reason,
            "size_bytes": os.stat(_sqlite_path(destination)).st_size,
        }
        _write_manifest(destination.with_suffix(".json"), manifest)
        _audit(engine, action, "DATABASE", str(source_path), backup_id, operator, reason, manifest)
    return manifest


def create_table_backup(engine: Engine, table_name: str, operator: str, role: str, reason: str, *, action: str = "TABLE_BACKUP") -> dict[str, Any]:
    operator = _require_super_admin(operator, role)
    reason = _require_reason(reason)
    source_path = _require_sqlite(engine)
    table_name = str(table_name or "").strip()
    _quote(table_name)
    if table_name not in inspect(engine).get_table_names():
        raise LookupError("Table not found")
    backup_id = uuid4().hex
    created_at = _now()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"table__{backup_id}.db"
    destination = _backup_root() / file_name
    with LOCK:
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(_sqlite_path(source_path))
        target = sqlite3.connect(_sqlite_path(destination))
        try:
            create_sql = source.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()[0]
            target.execute(create_sql)
            columns = [str(row[1]) for row in source.execute(f'PRAGMA table_info({_quote(table_name)})')]
            column_list = ",".join(_quote(column) for column in columns)
            placeholders = ",".join("?" for _ in columns)
            rows = source.execute(f"SELECT {column_list} FROM {_quote(table_name)}")
            target.executemany(
                f"INSERT INTO {_quote(table_name)} ({column_list}) VALUES ({placeholders})",
                rows,
            )
            row_count = int(source.execute(f"SELECT COUNT(*) FROM {_quote(table_name)}").fetchone()[0])
            target.commit()
        finally:
            target.close()
            source.close()
        manifest = {
            "backup_id": backup_id,
            "backup_type": "TABLE",
            "table_name": table_name,
            "table_description": table_description(table_name),
            "table_category": table_classification(table_name)["category_code"],
            "file_name": file_name,
            "created_at": created_at,
            "operator": operator,
            "reason": reason,
            "row_count": row_count,
            "size_bytes": os.stat(_sqlite_path(destination)).st_size,
        }
        _write_manifest(destination.with_suffix(".json"), manifest)
        _audit(engine, action, "TABLE", table_name, backup_id, operator, reason, manifest)
    return manifest


def restore_full_backup(engine: Engine, backup_id: str, operator: str, role: str, reason: str, confirmation: str) -> dict[str, Any]:
    operator = _require_super_admin(operator, role)
    reason = _require_reason(reason)
    if str(confirmation or "").strip() != "RESTORE DATABASE":
        raise ValueError("Confirmation text must be RESTORE DATABASE")
    manifest, backup_file = _load_backup(backup_id)
    if manifest.get("backup_type") != "FULL":
        raise ValueError("Selected backup is not a full-database backup")
    database_path = _require_sqlite(engine)
    with LOCK:
        safety = create_full_backup(engine, operator, role, f"Automatic safety backup before restore: {reason}", action="AUTO_BACKUP_BEFORE_FULL_RESTORE")
        engine.dispose()
        _sqlite_backup(backup_file, database_path)
        _audit(engine, "FULL_RESTORE", "DATABASE", str(database_path), backup_id, operator, reason, {"safety_backup_id": safety["backup_id"]})
    return {"status": "restored", "backup_id": backup_id, "safety_backup_id": safety["backup_id"]}


def restore_table_backup(engine: Engine, table_name: str, backup_id: str, operator: str, role: str, reason: str, confirmation: str) -> dict[str, Any]:
    operator = _require_super_admin(operator, role)
    reason = _require_reason(reason)
    table_name = str(table_name or "").strip()
    _quote(table_name)
    classification = table_classification(table_name)
    if not classification["can_restore"]:
        raise ValueError(f"Table restore is prohibited by classification policy: {classification['category_code']}")
    if str(confirmation or "").strip() != f"RESTORE TABLE {table_name}":
        raise ValueError(f"Confirmation text must be RESTORE TABLE {table_name}")
    manifest, backup_file = _load_backup(backup_id)
    if manifest.get("backup_type") != "TABLE" or manifest.get("table_name") != table_name:
        raise ValueError("Backup does not belong to the selected table")
    database_path = _require_sqlite(engine)
    with LOCK:
        safety = create_table_backup(engine, table_name, operator, role, f"Automatic safety backup before table restore: {reason}", action="AUTO_BACKUP_BEFORE_TABLE_RESTORE")
        connection = sqlite3.connect(_sqlite_path(database_path))
        try:
            connection.execute("ATTACH DATABASE ? AS restore_db", (_sqlite_path(backup_file),))
            current_columns = [str(row[1]) for row in connection.execute(f"PRAGMA main.table_info({_quote(table_name)})")]
            backup_columns = [str(row[1]) for row in connection.execute(f"PRAGMA restore_db.table_info({_quote(table_name)})")]
            if not backup_columns or any(column not in current_columns for column in backup_columns):
                raise ValueError("Backup columns are incompatible with the current table")
            column_list = ",".join(_quote(column) for column in backup_columns)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(f"DELETE FROM main.{_quote(table_name)}")
            connection.execute(
                f"INSERT INTO main.{_quote(table_name)} ({column_list}) "
                f"SELECT {column_list} FROM restore_db.{_quote(table_name)}"
            )
            row_count = int(connection.execute(f"SELECT COUNT(*) FROM main.{_quote(table_name)}").fetchone()[0])
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        _audit(engine, "TABLE_RESTORE", "TABLE", table_name, backup_id, operator, reason, {"safety_backup_id": safety["backup_id"], "row_count": row_count})
    return {"status": "restored", "table_name": table_name, "row_count": row_count, "backup_id": backup_id, "safety_backup_id": safety["backup_id"]}


def clear_table(engine: Engine, table_name: str, operator: str, role: str, reason: str, confirmation: str) -> dict[str, Any]:
    operator = _require_super_admin(operator, role)
    reason = _require_reason(reason)
    table_name = str(table_name or "").strip()
    _quote(table_name)
    classification = table_classification(table_name)
    if not classification["can_clear"]:
        raise ValueError(f"Table clear is prohibited by classification policy: {classification['category_code']}")
    if table_name not in inspect(engine).get_table_names():
        raise LookupError("Table not found")
    if str(confirmation or "").strip() != f"CLEAR TABLE {table_name}":
        raise ValueError(f"Confirmation text must be CLEAR TABLE {table_name}")
    with LOCK:
        safety = create_table_backup(engine, table_name, operator, role, f"Automatic safety backup before table clear: {reason}", action="AUTO_BACKUP_BEFORE_TABLE_CLEAR")
        with engine.begin() as connection:
            before_count = int(connection.execute(text(f"SELECT COUNT(*) FROM {_quote(table_name)}")).scalar_one())
            connection.execute(text(f"DELETE FROM {_quote(table_name)}"))
            if "sqlite_sequence" in inspect(engine).get_table_names():
                connection.execute(text("DELETE FROM sqlite_sequence WHERE name=:name"), {"name": table_name})
        _audit(engine, "TABLE_CLEAR", "TABLE", table_name, safety["backup_id"], operator, reason, {"deleted_rows": before_count})
    return {"status": "cleared", "table_name": table_name, "deleted_rows": before_count, "safety_backup_id": safety["backup_id"]}

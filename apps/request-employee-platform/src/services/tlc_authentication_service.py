from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.tlc_access_control_service import ensure_schema as ensure_access_schema
from src.services.tlc_mfa_security_service import check_login_mfa, record_login_anomaly  # TLC_MFA_SECURITY_AUDIT_R1


COOKIE_NAME = "tlc_session"
PASSWORD_ITERATIONS = 310_000
MAX_FAILURES = 5
LOCK_MINUTES = 15
SESSION_HOURS = 8
IDLE_MINUTES = 30


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None = None) -> str:
    return (value or now()).isoformat()


def ensure_schema(db: Session) -> None:
    ensure_access_schema(db)
    db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_auth_credential(
      user_id VARCHAR(64) PRIMARY KEY,password_hash VARCHAR(256) NOT NULL,
      password_salt VARCHAR(128) NOT NULL,password_iterations INTEGER NOT NULL,
      must_change_password INTEGER NOT NULL DEFAULT 1,failed_attempts INTEGER NOT NULL DEFAULT 0,
      locked_until VARCHAR(64) NOT NULL DEFAULT '',password_changed_at VARCHAR(64) NOT NULL,
      created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL)"""))
    db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_auth_session(
      id VARCHAR(64) PRIMARY KEY,token_hash VARCHAR(128) NOT NULL UNIQUE,user_id VARCHAR(64) NOT NULL,
      client_ip VARCHAR(128) NOT NULL DEFAULT '',user_agent VARCHAR(1000) NOT NULL DEFAULT '',
      created_at VARCHAR(64) NOT NULL,last_seen_at VARCHAR(64) NOT NULL,expires_at VARCHAR(64) NOT NULL,
      revoked_at VARCHAR(64) NOT NULL DEFAULT '',revoke_reason VARCHAR(500) NOT NULL DEFAULT '')"""))
    db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_auth_audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT,event_type VARCHAR(64) NOT NULL,user_id VARCHAR(64) NOT NULL DEFAULT '',
      login_id VARCHAR(128) NOT NULL DEFAULT '',client_ip VARCHAR(128) NOT NULL DEFAULT '',
      success INTEGER NOT NULL DEFAULT 0,detail VARCHAR(1000) NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL)"""))
    db.commit()


def _audit(db: Session, event: str, user_id: str = "", login_id: str = "", client_ip: str = "", success: bool = False, detail: str = "") -> None:
    db.execute(text("INSERT INTO tlc_auth_audit(event_type,user_id,login_id,client_ip,success,detail,created_at) VALUES(:event,:user,:login,:ip,:success,:detail,:created)"), {"event": event, "user": user_id, "login": login_id, "ip": client_ip, "success": 1 if success else 0, "detail": detail[:1000], "created": iso()})


def _password_policy(password: str) -> None:
    if len(password) < 12 or not any(x.islower() for x in password) or not any(x.isupper() for x in password) or not any(x.isdigit() for x in password):
        raise ValueError("密码至少12位，并且必须包含大写字母、小写字母和数字")


def _hash_password(password: str, salt: bytes, iterations: int = PASSWORD_ITERATIONS) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _parse(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def bootstrap(db: Session, employee_no: str, login_id: str, name_zh: str, password: str, client_ip: str) -> dict:
    ensure_schema(db)
    if db.execute(text("SELECT COUNT(*) FROM tlc_auth_credential")).scalar_one() > 0:
        raise ValueError("初始超级管理员已经设置")
    _password_policy(password)
    employee_no = employee_no.strip();login_id = login_id.strip()
    if not employee_no or not login_id:
        raise ValueError("员工编号和登录ID为必填")
    user = db.execute(text("SELECT id FROM tlc_user_master WHERE employee_no=:employee OR login_id=:login"), {"employee": employee_no, "login": login_id}).first()
    user_id = str(user[0]) if user else uuid4().hex
    stamp = iso()
    if not user:
        db.execute(text("""INSERT INTO tlc_user_master(id,employee_no,name_en,name_ja,name_zh,email,mobile,login_id,legal_entity_id,department_id,active,valid_from,valid_to,created_at,updated_at)
          VALUES(:id,:employee,'','',:name,'','',:login,'','',1,'','',:stamp,:stamp)"""), {"id": user_id, "employee": employee_no, "name": name_zh.strip(), "login": login_id, "stamp": stamp})
    salt = secrets.token_bytes(32)
    db.execute(text("INSERT INTO tlc_auth_credential VALUES(:user,:hash,:salt,:iterations,1,0,'',:stamp,:stamp,:stamp)"), {"user": user_id, "hash": _hash_password(password, salt), "salt": salt.hex(), "iterations": PASSWORD_ITERATIONS, "stamp": stamp})
    db.execute(text("INSERT OR IGNORE INTO tlc_user_role(id,user_id,role_code,created_at,created_by) VALUES(:id,:user,'SUPER_ADMIN',:stamp,'AUTH_BOOTSTRAP')"), {"id": uuid4().hex, "user": user_id, "stamp": stamp})
    _audit(db, "BOOTSTRAP_SUPER_ADMIN", user_id, login_id, client_ip, True)
    db.commit()
    return {"user_id": user_id, "login_id": login_id, "must_change_password": True}


def login(db: Session, login_id: str, password: str, client_ip: str, user_agent: str, mfa_code: str = "") -> dict:
    ensure_schema(db)
    login_id = login_id.strip()
    row = db.execute(text("""SELECT u.*,c.password_hash,c.password_salt,c.password_iterations,c.must_change_password,
      c.failed_attempts,c.locked_until FROM tlc_user_master u LEFT JOIN tlc_auth_credential c ON c.user_id=u.id
      WHERE u.login_id=:login"""), {"login": login_id}).first()
    if not row or not row._mapping.get("password_hash"):
        _audit(db, "LOGIN_FAILED", "", login_id, client_ip, False, "UNKNOWN_ACCOUNT");db.commit();raise PermissionError("登录ID或密码不正确")
    user = dict(row._mapping);current = now();locked_until = _parse(str(user.get("locked_until") or ""))
    if locked_until and locked_until > current:
        _audit(db, "LOGIN_BLOCKED", user["id"], login_id, client_ip, False, "ACCOUNT_LOCKED");db.commit();raise PermissionError("账号因密码错误暂时锁定")
    if not bool(user["active"]):
        _audit(db, "LOGIN_BLOCKED", user["id"], login_id, client_ip, False, "ACCOUNT_DISABLED");db.commit();raise PermissionError("账号已停用")
    valid_from = str(user.get("valid_from") or "");valid_to = str(user.get("valid_to") or "");today = current.date().isoformat()
    if (valid_from and today < valid_from) or (valid_to and today > valid_to):
        _audit(db, "LOGIN_BLOCKED", user["id"], login_id, client_ip, False, "OUTSIDE_VALID_PERIOD");db.commit();raise PermissionError("账号不在有效期间")
    actual = _hash_password(password, bytes.fromhex(user["password_salt"]), int(user["password_iterations"]))
    if not hmac.compare_digest(actual, user["password_hash"]):
        failures = int(user["failed_attempts"] or 0) + 1;lock_value = iso(current + timedelta(minutes=LOCK_MINUTES)) if failures >= MAX_FAILURES else ""
        db.execute(text("UPDATE tlc_auth_credential SET failed_attempts=:failures,locked_until=:locked,updated_at=:updated WHERE user_id=:user"), {"failures": failures, "locked": lock_value, "updated": iso(), "user": user["id"]})
        _audit(db, "LOGIN_FAILED", user["id"], login_id, client_ip, False, f"BAD_PASSWORD:{failures}");db.commit();raise PermissionError("登录ID或密码不正确")
    db.execute(text("UPDATE tlc_auth_credential SET failed_attempts=0,locked_until='',updated_at=:updated WHERE user_id=:user"), {"updated": iso(), "user": user["id"]})
    check_login_mfa(db, user["id"], mfa_code, client_ip)
    token = secrets.token_urlsafe(48);session_id = uuid4().hex;expires = current + timedelta(hours=int(os.getenv("TLC_SESSION_HOURS", str(SESSION_HOURS))))
    db.execute(text("INSERT INTO tlc_auth_session VALUES(:id,:hash,:user,:ip,:agent,:created,:seen,:expires,'','')"), {"id": session_id, "hash": _token_hash(token), "user": user["id"], "ip": client_ip, "agent": user_agent[:1000], "created": iso(current), "seen": iso(current), "expires": iso(expires)})
    _audit(db, "LOGIN_SUCCESS", user["id"], login_id, client_ip, True);db.commit()
    record_login_anomaly(db, user["id"], client_ip)
    return {"token": token, "session_id": session_id, "user_id": user["id"], "must_change_password": bool(user["must_change_password"]), "expires_at": iso(expires)}


def current_session(db: Session, token: str, touch: bool = True) -> dict | None:
    ensure_schema(db)
    if not token:return None
    row = db.execute(text("""SELECT s.*,u.employee_no,u.login_id,u.name_en,u.name_ja,u.name_zh,u.email,u.mobile,u.legal_entity_id,u.department_id,u.active,c.must_change_password
      FROM tlc_auth_session s JOIN tlc_user_master u ON u.id=s.user_id JOIN tlc_auth_credential c ON c.user_id=u.id
      WHERE s.token_hash=:hash"""), {"hash": _token_hash(token)}).first()
    if not row:return None
    data = dict(row._mapping);current = now();last_seen = _parse(data["last_seen_at"]);expires = _parse(data["expires_at"])
    idle_limit = timedelta(minutes=int(os.getenv("TLC_SESSION_IDLE_MINUTES", str(IDLE_MINUTES))))
    if data["revoked_at"] or not bool(data["active"]) or not expires or expires <= current or not last_seen or current - last_seen > idle_limit:
        if not data["revoked_at"]:db.execute(text("UPDATE tlc_auth_session SET revoked_at=:now,revoke_reason='EXPIRED' WHERE id=:id"), {"now": iso(), "id": data["id"]});db.commit()
        return None
    if touch:db.execute(text("UPDATE tlc_auth_session SET last_seen_at=:seen WHERE id=:id"), {"seen": iso(current), "id": data["id"]});db.commit();data["last_seen_at"] = iso(current)
    data.pop("token_hash", None)
    return data


def logout(db: Session, token: str, client_ip: str) -> None:
    ensure_schema(db);session = current_session(db, token, touch=False)
    if session:
        db.execute(text("UPDATE tlc_auth_session SET revoked_at=:now,revoke_reason='LOGOUT' WHERE id=:id"), {"now": iso(), "id": session["id"]});_audit(db, "LOGOUT", session["user_id"], session["login_id"], client_ip, True);db.commit()


def change_password(db: Session, token: str, current_password: str, new_password: str, client_ip: str) -> dict:
    session = current_session(db, token, touch=False)
    if not session:raise PermissionError("登录会话无效")
    _password_policy(new_password)
    credential = db.execute(text("SELECT * FROM tlc_auth_credential WHERE user_id=:user"), {"user": session["user_id"]}).first()._mapping
    actual = _hash_password(current_password, bytes.fromhex(credential["password_salt"]), int(credential["password_iterations"]))
    if not hmac.compare_digest(actual, credential["password_hash"]):raise PermissionError("当前密码不正确")
    salt = secrets.token_bytes(32);stamp = iso()
    db.execute(text("UPDATE tlc_auth_credential SET password_hash=:hash,password_salt=:salt,password_iterations=:iterations,must_change_password=0,password_changed_at=:stamp,updated_at=:stamp WHERE user_id=:user"), {"hash": _hash_password(new_password, salt), "salt": salt.hex(), "iterations": PASSWORD_ITERATIONS, "stamp": stamp, "user": session["user_id"]})
    db.execute(text("UPDATE tlc_auth_session SET revoked_at=:stamp,revoke_reason='PASSWORD_CHANGED' WHERE user_id=:user AND id<>:current AND revoked_at=''"), {"stamp": stamp, "user": session["user_id"], "current": session["id"]})
    _audit(db, "PASSWORD_CHANGED", session["user_id"], session["login_id"], client_ip, True);db.commit();return {"changed": True, "other_sessions_revoked": True}


def audit_rows(db: Session, limit: int = 200) -> list[dict]:
    ensure_schema(db);rows = db.execute(text("SELECT * FROM tlc_auth_audit ORDER BY id DESC LIMIT :limit"), {"limit": min(max(int(limit), 1), 1000)}).all();return [dict(x._mapping) for x in rows]

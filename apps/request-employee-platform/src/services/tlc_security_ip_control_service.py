from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import ip_address, ip_network
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


MODULE_CODE = "SECURITY_IP_CONTROL"
ACTIONS = ("VIEW", "MAINTAIN")
SCOPE_TYPES = {"GLOBAL", "LOCAL", "LEGAL_ENTITY", "DEPARTMENT", "USER"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(db: Session) -> None:
    db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_ip_access_rule(
      id VARCHAR(64) PRIMARY KEY,name VARCHAR(255) NOT NULL,network VARCHAR(128) NOT NULL,
      decision VARCHAR(16) NOT NULL,scope_type VARCHAR(32) NOT NULL,scope_id VARCHAR(128) NOT NULL DEFAULT '',
      enabled INTEGER NOT NULL DEFAULT 1,note VARCHAR(1000) NOT NULL DEFAULT '',
      created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL)"""))
    db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_trusted_proxy(
      id VARCHAR(64) PRIMARY KEY,name VARCHAR(255) NOT NULL,network VARCHAR(128) NOT NULL,
      enabled INTEGER NOT NULL DEFAULT 1,note VARCHAR(1000) NOT NULL DEFAULT '',
      created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL)"""))
    db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_ip_access_audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT,user_id VARCHAR(64) NOT NULL DEFAULT '',
      direct_ip VARCHAR(128) NOT NULL DEFAULT '',effective_ip VARCHAR(128) NOT NULL DEFAULT '',
      forwarded_for VARCHAR(1000) NOT NULL DEFAULT '',path VARCHAR(1000) NOT NULL DEFAULT '',
      method VARCHAR(16) NOT NULL DEFAULT '',decision VARCHAR(32) NOT NULL,matched_rule_id VARCHAR(64) NOT NULL DEFAULT '',
      would_block INTEGER NOT NULL DEFAULT 0,detail VARCHAR(1000) NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL)"""))
    stamp = now()
    db.execute(text("""INSERT OR IGNORE INTO tlc_permission_module
      (id,module_code,name_zh,active,sort_order,created_at,updated_at)
      VALUES(:id,:code,'IP访问控制',1,45,:stamp,:stamp)"""), {"id": uuid4().hex, "code": MODULE_CODE, "stamp": stamp})
    for action in ACTIONS:
        db.execute(text("""INSERT OR IGNORE INTO tlc_role_permission
          (id,role_code,module_code,action_code,data_scope,allowed,updated_at,updated_by)
          VALUES(:id,'SUPER_ADMIN',:module,:action,'ALL',1,:stamp,'SYSTEM')"""),
          {"id": uuid4().hex, "module": MODULE_CODE, "action": action, "stamp": stamp})
    db.commit()


def _network(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError("IP或CIDR不能为空")
    try:
        if "/" not in value:
            address = ip_address(value)
            value = f"{address}/{32 if address.version == 4 else 128}"
        return str(ip_network(value, strict=False))
    except ValueError as exc:
        raise ValueError("IP或CIDR格式不正确") from exc


def _row(row) -> dict:
    return dict(row._mapping)


def overview(db: Session, limit: int = 500) -> dict:
    ensure_schema(db)
    rules = [_row(x) for x in db.execute(text("SELECT * FROM tlc_ip_access_rule ORDER BY enabled DESC,decision DESC,scope_type,name LIMIT :n"), {"n": min(max(limit,1),2000)}).all()]
    proxies = [_row(x) for x in db.execute(text("SELECT * FROM tlc_trusted_proxy ORDER BY enabled DESC,name")).all()]
    audit = [_row(x) for x in db.execute(text("SELECT * FROM tlc_ip_access_audit ORDER BY id DESC LIMIT 200")).all()]
    return {"mode":"MONITOR","rules":rules,"trusted_proxies":proxies,"audit":audit,"scope_types":sorted(SCOPE_TYPES)}


def save_rule(db: Session, payload: dict) -> dict:
    ensure_schema(db)
    record_id = str(payload.get("id") or uuid4().hex)
    name = str(payload.get("name") or "").strip()
    decision = str(payload.get("decision") or "").upper()
    scope_type = str(payload.get("scope_type") or "GLOBAL").upper()
    scope_id = str(payload.get("scope_id") or "").strip()
    if not name or decision not in {"ALLOW","DENY"} or scope_type not in SCOPE_TYPES:
        raise ValueError("名称、ALLOW/DENY及适用范围必须正确填写")
    if scope_type in {"LEGAL_ENTITY","DEPARTMENT","USER"} and not scope_id:
        raise ValueError("法人、部门或人员范围必须填写范围ID")
    stamp=now();values={"id":record_id,"name":name,"network":_network(payload.get("network","")),"decision":decision,"scope":scope_type,"scope_id":scope_id,"enabled":1 if payload.get("enabled",True) else 0,"note":str(payload.get("note")or""),"stamp":stamp}
    db.execute(text("""INSERT INTO tlc_ip_access_rule VALUES(:id,:name,:network,:decision,:scope,:scope_id,:enabled,:note,:stamp,:stamp)
      ON CONFLICT(id) DO UPDATE SET name=:name,network=:network,decision=:decision,scope_type=:scope,scope_id=:scope_id,enabled=:enabled,note=:note,updated_at=:stamp"""),values)
    db.commit();return {"saved":True,"id":record_id,"network":values["network"]}


def delete_rule(db: Session, record_id: str) -> dict:
    ensure_schema(db);result=db.execute(text("DELETE FROM tlc_ip_access_rule WHERE id=:id"),{"id":record_id});db.commit()
    if not result.rowcount:raise LookupError("IP访问规则不存在")
    return {"deleted":True,"id":record_id}


def save_proxy(db: Session, payload: dict) -> dict:
    ensure_schema(db);record_id=str(payload.get("id")or uuid4().hex);name=str(payload.get("name")or"").strip()
    if not name:raise ValueError("可信代理名称不能为空")
    stamp=now();values={"id":record_id,"name":name,"network":_network(payload.get("network","")),"enabled":1 if payload.get("enabled",True) else 0,"note":str(payload.get("note")or""),"stamp":stamp}
    db.execute(text("""INSERT INTO tlc_trusted_proxy VALUES(:id,:name,:network,:enabled,:note,:stamp,:stamp)
      ON CONFLICT(id) DO UPDATE SET name=:name,network=:network,enabled=:enabled,note=:note,updated_at=:stamp"""),values);db.commit()
    return {"saved":True,"id":record_id,"network":values["network"]}


def delete_proxy(db: Session, record_id: str) -> dict:
    ensure_schema(db);result=db.execute(text("DELETE FROM tlc_trusted_proxy WHERE id=:id"),{"id":record_id});db.commit()
    if not result.rowcount:raise LookupError("可信代理不存在")
    return {"deleted":True,"id":record_id}


def _contains(network: str, address: str) -> bool:
    try:return ip_address(address) in ip_network(network,strict=False)
    except ValueError:return False


def _effective_ip(db: Session, direct_ip: str, forwarded_for: str) -> tuple[str,bool]:
    trusted = any(_contains(str(x[0]),direct_ip) for x in db.execute(text("SELECT network FROM tlc_trusted_proxy WHERE enabled=1")).all())
    if trusted and forwarded_for:
        candidate=forwarded_for.split(",")[0].strip()
        try:ip_address(candidate);return candidate,True
        except ValueError:pass
    return direct_ip,False


def _scope_matches(rule: dict, session: dict, direct_ip: str) -> bool:
    kind=rule["scope_type"];scope_id=str(rule.get("scope_id")or"")
    if kind=="GLOBAL":return True
    if kind=="LOCAL":return direct_ip in {"127.0.0.1","::1"}
    if kind=="LEGAL_ENTITY":return scope_id==str(session.get("legal_entity_id")or"")
    if kind=="DEPARTMENT":return scope_id==str(session.get("department_id")or"")
    if kind=="USER":return scope_id==str(session.get("user_id")or"")
    return False


def monitor_request(db: Session, session: dict, method: str, path: str, direct_ip: str, forwarded_for: str = "", record: bool = True) -> dict:
    ensure_schema(db);effective,trusted=_effective_ip(db,direct_ip,forwarded_for)
    rules=[_row(x) for x in db.execute(text("SELECT * FROM tlc_ip_access_rule WHERE enabled=1")).all()]
    applicable=[x for x in rules if _scope_matches(x,session,direct_ip)]
    matched=[x for x in applicable if _contains(x["network"],effective)]
    deny=next((x for x in matched if x["decision"]=="DENY"),None)
    allow=next((x for x in matched if x["decision"]=="ALLOW"),None)
    has_allow=any(x["decision"]=="ALLOW" for x in applicable)
    would_block=bool(deny or (has_allow and not allow));decision="WOULD_DENY" if would_block else ("ALLOW_MATCH" if allow else "NO_RESTRICTION")
    matched_rule=deny or allow;detail="MONITOR_ONLY; request was not blocked"
    if record:
        db.execute(text("""INSERT INTO tlc_ip_access_audit(user_id,direct_ip,effective_ip,forwarded_for,path,method,decision,matched_rule_id,would_block,detail,created_at)
          VALUES(:user,:direct,:effective,:forwarded,:path,:method,:decision,:rule,:block,:detail,:stamp)"""),{"user":str(session.get("user_id")or""),"direct":direct_ip,"effective":effective,"forwarded":forwarded_for[:1000],"path":path[:1000],"method":method,"decision":decision,"rule":str(matched_rule["id"] if matched_rule else ""),"block":1 if would_block else 0,"detail":detail+("; trusted proxy" if trusted else ""),"stamp":now()});db.commit()
    return {"mode":"MONITOR","direct_ip":direct_ip,"effective_ip":effective,"trusted_proxy":trusted,"decision":decision,"would_block":would_block,"blocked":False}

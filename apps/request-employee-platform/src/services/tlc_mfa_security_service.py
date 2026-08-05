from __future__ import annotations

import base64, hashlib, hmac, secrets, struct, time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.services.tlc_access_control_service import ensure_schema as ensure_access_schema

STEP_UP_MINUTES=5

def now():return datetime.now(timezone.utc)
def iso(value=None):return (value or now()).isoformat()

def ensure_schema(db:Session):
 ensure_access_schema(db)
 db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_mfa_totp(user_id VARCHAR(64) PRIMARY KEY,secret VARCHAR(128) NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,last_counter INTEGER NOT NULL DEFAULT -1,created_at VARCHAR(64) NOT NULL,verified_at VARCHAR(64) NOT NULL DEFAULT '')"""))
 db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_security_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,event_type VARCHAR(64) NOT NULL,user_id VARCHAR(64) NOT NULL DEFAULT '',client_ip VARCHAR(128) NOT NULL DEFAULT '',success INTEGER NOT NULL DEFAULT 0,detail VARCHAR(1000) NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL)"""))
 db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_step_up_token(id VARCHAR(64) PRIMARY KEY,token_hash VARCHAR(128) NOT NULL UNIQUE,user_id VARCHAR(64) NOT NULL,purpose VARCHAR(500) NOT NULL DEFAULT '*',created_at VARCHAR(64) NOT NULL,expires_at VARCHAR(64) NOT NULL,used_at VARCHAR(64) NOT NULL DEFAULT '')"""))
 db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_security_rate_limit(bucket_key VARCHAR(500) PRIMARY KEY,window_started_at VARCHAR(64) NOT NULL,request_count INTEGER NOT NULL DEFAULT 0)"""))
 stamp=iso();db.execute(text("INSERT OR IGNORE INTO tlc_permission_module(id,module_code,name_zh,active,sort_order,created_at,updated_at) VALUES(:id,'SECURITY_AUDIT','MFA与高级安全',1,46,:s,:s)"),{"id":uuid4().hex,"s":stamp})
 for action in ("VIEW","MAINTAIN"):
  db.execute(text("INSERT OR IGNORE INTO tlc_role_permission(id,role_code,module_code,action_code,data_scope,allowed,updated_at,updated_by) VALUES(:id,'SUPER_ADMIN','SECURITY_AUDIT',:a,'ALL',1,:s,'SYSTEM')"),{"id":uuid4().hex,"a":action,"s":stamp})
 db.commit()

def audit(db,event,user="",ip="",success=False,detail=""):
 ensure_schema(db);db.execute(text("INSERT INTO tlc_security_audit(event_type,user_id,client_ip,success,detail,created_at) VALUES(:e,:u,:i,:s,:d,:c)"),{"e":event,"u":user,"i":ip,"s":1 if success else 0,"d":detail[:1000],"c":iso()});db.commit()

def _secret():return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
def _counter(at=None):return int((at or time.time())//30)
def totp(secret,counter):
 key=base64.b32decode(secret+"="*((8-len(secret)%8)%8));digest=hmac.new(key,struct.pack(">Q",counter),hashlib.sha1).digest();offset=digest[-1]&15;value=(struct.unpack(">I",digest[offset:offset+4])[0]&0x7fffffff)%1000000;return f"{value:06d}"

def mfa_status(db,user):
 ensure_schema(db);row=db.execute(text("SELECT enabled,created_at,verified_at FROM tlc_mfa_totp WHERE user_id=:u"),{"u":user}).first();return {"configured":bool(row),"enabled":bool(row[0]) if row else False,"created_at":row[1] if row else "","verified_at":row[2] if row else ""}

def setup_mfa(db,user,login_id):
 ensure_schema(db);existing=db.execute(text("SELECT enabled FROM tlc_mfa_totp WHERE user_id=:u"),{"u":user}).first()
 if existing and bool(existing[0]):raise ValueError("MFA is already enabled; disable it before resetting the secret")
 secret=_secret();stamp=iso();db.execute(text("INSERT INTO tlc_mfa_totp VALUES(:u,:secret,0,-1,:s,'') ON CONFLICT(user_id) DO UPDATE SET secret=:secret,enabled=0,last_counter=-1,created_at=:s,verified_at=''"),{"u":user,"secret":secret,"s":stamp});db.commit();return {"secret":secret,"otpauth_uri":f"otpauth://totp/{quote('TLC Platform:'+login_id)}?secret={secret}&issuer={quote('TLC Platform')}&algorithm=SHA1&digits=6&period=30"}

def verify_totp(db,user,code,consume=True):
 ensure_schema(db);row=db.execute(text("SELECT secret,last_counter FROM tlc_mfa_totp WHERE user_id=:u"),{"u":user}).first()
 if not row or not str(code).isdigit() or len(str(code))!=6:return False
 current=_counter()
 for counter in range(current-1,current+2):
  if hmac.compare_digest(totp(row[0],counter),str(code)) and (not consume or counter>int(row[1])):
   if consume:db.execute(text("UPDATE tlc_mfa_totp SET last_counter=:c WHERE user_id=:u"),{"c":counter,"u":user});db.commit()
   return True
 return False

def enable_mfa(db,user,code,ip=""):
 if not verify_totp(db,user,code):audit(db,"MFA_ENABLE_FAILED",user,ip,False);raise ValueError("MFA验证码不正确")
 stamp=iso();db.execute(text("UPDATE tlc_mfa_totp SET enabled=1,verified_at=:s WHERE user_id=:u"),{"s":stamp,"u":user});audit(db,"MFA_ENABLED",user,ip,True);db.commit();return {"enabled":True}

def disable_mfa(db,user,code,ip=""):
 if not verify_totp(db,user,code):audit(db,"MFA_DISABLE_FAILED",user,ip,False);raise ValueError("MFA验证码不正确")
 db.execute(text("UPDATE tlc_mfa_totp SET enabled=0 WHERE user_id=:u"),{"u":user});audit(db,"MFA_DISABLED",user,ip,True);db.commit();return {"enabled":False}

def check_login_mfa(db,user,code,ip=""):
 ensure_schema(db);row=db.execute(text("SELECT enabled FROM tlc_mfa_totp WHERE user_id=:u"),{"u":user}).first()
 if not row or not bool(row[0]):return
 if not code: audit(db,"LOGIN_MFA_REQUIRED",user,ip,False);raise PermissionError("MFA code required")
 if not verify_totp(db,user,code):audit(db,"LOGIN_MFA_FAILED",user,ip,False);raise PermissionError("MFA code is invalid")
 audit(db,"LOGIN_MFA_SUCCESS",user,ip,True)

def rate_limit(db,key,limit,window_seconds):
 ensure_schema(db);stamp=now();row=db.execute(text("SELECT window_started_at,request_count FROM tlc_security_rate_limit WHERE bucket_key=:k"),{"k":key}).first()
 if not row or stamp-datetime.fromisoformat(row[0])>=timedelta(seconds=window_seconds):db.execute(text("INSERT INTO tlc_security_rate_limit VALUES(:k,:s,1) ON CONFLICT(bucket_key) DO UPDATE SET window_started_at=:s,request_count=1"),{"k":key,"s":iso(stamp)});db.commit();return True
 count=int(row[1])+1;db.execute(text("UPDATE tlc_security_rate_limit SET request_count=:c WHERE bucket_key=:k"),{"c":count,"k":key});db.commit();return count<=limit

def record_login_anomaly(db,user,ip):
 ensure_schema(db);previous=db.execute(text("SELECT client_ip FROM tlc_security_audit WHERE user_id=:u AND event_type IN ('LOGIN_OBSERVED','LOGIN_ANOMALY_NEW_IP') AND success=1 ORDER BY id DESC LIMIT 1"),{"u":user}).first();changed=bool(previous and previous[0] and previous[0]!=ip);audit(db,"LOGIN_ANOMALY_NEW_IP" if changed else "LOGIN_OBSERVED",user,ip,True,"Previous IP: "+str(previous[0]) if changed else "");return {"new_ip":changed}

def list_sessions(db,user,all_users=False):
 ensure_schema(db);where="" if all_users else "WHERE s.user_id=:u";rows=db.execute(text(f"SELECT s.id,s.user_id,u.login_id,s.client_ip,s.user_agent,s.created_at,s.last_seen_at,s.expires_at,s.revoked_at,s.revoke_reason FROM tlc_auth_session s JOIN tlc_user_master u ON u.id=s.user_id {where} ORDER BY s.created_at DESC LIMIT 1000"),{"u":user}).all();return [dict(x._mapping) for x in rows]

def revoke_session(db,session_id,actor,can_all=False):
 row=db.execute(text("SELECT user_id,revoked_at FROM tlc_auth_session WHERE id=:id"),{"id":session_id}).first()
 if not row:raise LookupError("会话不存在")
 if row[0]!=actor and not can_all:raise PermissionError("不能强制退出其他用户")
 if not row[1]:db.execute(text("UPDATE tlc_auth_session SET revoked_at=:s,revoke_reason='FORCED_LOGOUT' WHERE id=:id"),{"s":iso(),"id":session_id});audit(db,"SESSION_FORCED_LOGOUT",actor,"",True,session_id);db.commit()
 return {"revoked":True,"session_id":session_id}

def verify_password(db,user,password):
 from src.services.tlc_authentication_service import _hash_password
 row=db.execute(text("SELECT password_hash,password_salt,password_iterations FROM tlc_auth_credential WHERE user_id=:u"),{"u":user}).first()
 return bool(row and hmac.compare_digest(_hash_password(password,bytes.fromhex(row[1]),int(row[2])),row[0]))

def create_step_up(db,user,password,code,ip):
 if not verify_password(db,user,password):audit(db,"STEP_UP_FAILED",user,ip,False,"BAD_PASSWORD");raise PermissionError("密码不正确")
 status=mfa_status(db,user)
 if status["enabled"] and not verify_totp(db,user,code):audit(db,"STEP_UP_FAILED",user,ip,False,"BAD_MFA");raise PermissionError("MFA验证码不正确")
 token=secrets.token_urlsafe(40);stamp=now();db.execute(text("INSERT INTO tlc_step_up_token VALUES(:id,:hash,:u,'*',:c,:e,'')"),{"id":uuid4().hex,"hash":hashlib.sha256(token.encode()).hexdigest(),"u":user,"c":iso(stamp),"e":iso(stamp+timedelta(minutes=STEP_UP_MINUTES))});audit(db,"STEP_UP_SUCCESS",user,ip,True);db.commit();return {"token":token,"expires_in":STEP_UP_MINUTES*60}

def valid_step_up(db,user,token):
 ensure_schema(db)
 if not token:return False
 row=db.execute(text("SELECT expires_at,used_at FROM tlc_step_up_token WHERE token_hash=:h AND user_id=:u"),{"h":hashlib.sha256(token.encode()).hexdigest(),"u":user}).first();return bool(row and not row[1] and datetime.fromisoformat(row[0])>now())

def security_audit(db,limit=500):
 ensure_schema(db);return [dict(x._mapping) for x in db.execute(text("SELECT * FROM tlc_security_audit ORDER BY id DESC LIMIT :n"),{"n":min(max(int(limit),1),2000)}).all()]

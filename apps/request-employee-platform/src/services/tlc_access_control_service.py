from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session

ROLES=[("SUPER_ADMIN","超级管理员"),("ADMIN","管理员"),("SECURITY_ADMIN","安全管理员"),("USER_ADMIN","人员管理员"),("DATABASE_ADMIN","数据库管理员"),("AUDITOR","审计员"),("MANAGER","部门经理"),("REQUEST_OPERATOR","请求书操作员"),("BUSINESS_REVIEWER","请求书业务审核员"),("SALES_OPERATOR","销售操作员"),("CUSTOMER_OPERATOR","客户操作员"),("BANK_OPERATOR","银行操作员"),("ACCOUNTING_OPERATOR","财务操作员"),("VIEWER","只读用户")]
MODULES=[("DASHBOARD","Dashboard"),("LEGAL_ENTITY_MASTER","法人主数据"),("USER_PERMISSION","人员与权限"),("SYSTEM_PARAMETER","系统参数"),("DATABASE_MAINTENANCE","数据库维护"),("CUSTOMER_MASTER","客户主数据"),("CUSTOMER_CANDIDATE","客户候选提取与审核"),("BANK_MASTER","银行与账户"),("REQUEST_BATCH","请求书导入Batch"),("REQUEST_FILE_REVIEW","文件核对Review"),("REQUEST_BUSINESS_REVIEW","请求书业务审核"),("FORMAL_SALES_LEDGER","正式销售台账"),("SALES_STATISTICS","销售统计"),("BANK_IMPORT","银行流水导入"),("BANK_CUSTOMER_MATCHING","银行客户匹配"),("RECEIVABLE","应收管理"),("CUSTOMER_RECONCILIATION","客户对账"),("MONTHLY_WORKFLOW","月度流程"),("MONTHLY_CLOSE","月结"),("OPERATIONAL_EXCEPTION","异常处理"),("AUDIT_LOG","操作日志")]
ACTIONS=("VIEW","EDIT","DELETE","EXECUTE","APPROVE","EXPORT","MAINTAIN")
SCOPES=("SELF","DEPARTMENT","LEGAL_ENTITY","ALL")
def now():return datetime.now(timezone.utc).isoformat()
def ensure_schema(db:Session):
 db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_department_master(id VARCHAR(64) PRIMARY KEY,department_code VARCHAR(64) NOT NULL UNIQUE,name_zh VARCHAR(255) NOT NULL,name_ja VARCHAR(255) NOT NULL DEFAULT '',name_en VARCHAR(255) NOT NULL DEFAULT '',legal_entity_id VARCHAR(50) NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1,created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL)"""))
 db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_user_master(id VARCHAR(64) PRIMARY KEY,employee_no VARCHAR(64) NOT NULL UNIQUE,name_en VARCHAR(255) NOT NULL DEFAULT '',name_ja VARCHAR(255) NOT NULL DEFAULT '',name_zh VARCHAR(255) NOT NULL DEFAULT '',email VARCHAR(500) NOT NULL DEFAULT '',mobile VARCHAR(128) NOT NULL DEFAULT '',login_id VARCHAR(128) NOT NULL UNIQUE,legal_entity_id VARCHAR(50) NOT NULL DEFAULT '',department_id VARCHAR(64) NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1,valid_from VARCHAR(32) NOT NULL DEFAULT '',valid_to VARCHAR(32) NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL)"""))
 db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_role_master(id VARCHAR(64) PRIMARY KEY,role_code VARCHAR(64) NOT NULL UNIQUE,name_zh VARCHAR(255) NOT NULL,description TEXT NOT NULL DEFAULT '',system_role INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL)"""))
 db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_permission_module(id VARCHAR(64) PRIMARY KEY,module_code VARCHAR(128) NOT NULL UNIQUE,name_zh VARCHAR(255) NOT NULL,active INTEGER NOT NULL DEFAULT 1,sort_order INTEGER NOT NULL DEFAULT 0,created_at VARCHAR(64) NOT NULL,updated_at VARCHAR(64) NOT NULL)"""))
 db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_user_role(id VARCHAR(64) PRIMARY KEY,user_id VARCHAR(64) NOT NULL,role_code VARCHAR(64) NOT NULL,created_at VARCHAR(64) NOT NULL,created_by VARCHAR(255) NOT NULL DEFAULT '',UNIQUE(user_id,role_code))"""))
 db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_role_permission(id VARCHAR(64) PRIMARY KEY,role_code VARCHAR(64) NOT NULL,module_code VARCHAR(128) NOT NULL,action_code VARCHAR(32) NOT NULL,data_scope VARCHAR(32) NOT NULL DEFAULT 'LEGAL_ENTITY',allowed INTEGER NOT NULL DEFAULT 1,updated_at VARCHAR(64) NOT NULL,updated_by VARCHAR(255) NOT NULL DEFAULT '',UNIQUE(role_code,module_code,action_code))"""))
 db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_permission_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor VARCHAR(255) NOT NULL DEFAULT '',target_type VARCHAR(64) NOT NULL,target_id VARCHAR(128) NOT NULL,action VARCHAR(64) NOT NULL,detail TEXT NOT NULL DEFAULT '',created_at VARCHAR(64) NOT NULL)"""))
 stamp=now()
 for code,name in ROLES:db.execute(text("INSERT OR IGNORE INTO tlc_role_master VALUES(:id,:code,:name,'',1,1,:c,:u)"),{"id":uuid4().hex,"code":code,"name":name,"c":stamp,"u":stamp})
 for i,(code,name) in enumerate(MODULES):db.execute(text("INSERT OR IGNORE INTO tlc_permission_module VALUES(:id,:code,:name,1,:sort,:c,:u)"),{"id":uuid4().hex,"code":code,"name":name,"sort":i*10,"c":stamp,"u":stamp})
 for module,_ in MODULES:
  for action in ACTIONS:db.execute(text("INSERT OR IGNORE INTO tlc_role_permission VALUES(:id,'SUPER_ADMIN',:module,:action,'ALL',1,:u,'SYSTEM')"),{"id":uuid4().hex,"module":module,"action":action,"u":stamp})
 db.commit()
def rows(db:Session,table:str,order:str):ensure_schema(db);return[dict(x._mapping) for x in db.execute(text(f"SELECT * FROM {table} ORDER BY {order}")).all()]
def overview(db:Session):return{"departments":rows(db,"tlc_department_master","department_code"),"users":rows(db,"tlc_user_master","employee_no"),"roles":rows(db,"tlc_role_master","role_code"),"modules":rows(db,"tlc_permission_module","sort_order,module_code"),"permissions":rows(db,"tlc_role_permission","role_code,module_code,action_code"),"user_roles":rows(db,"tlc_user_role","user_id,role_code"),"actions":ACTIONS,"scopes":SCOPES}
def audit(db:Session,actor,target_type,target_id,action,detail=""):db.execute(text("INSERT INTO tlc_permission_audit(actor,target_type,target_id,action,detail,created_at) VALUES(:a,:t,:i,:x,:d,:c)"),{"a":actor,"t":target_type,"i":target_id,"x":action,"d":detail,"c":now()})
def save_department(db:Session,p:dict):
 ensure_schema(db)
 code=str(p.get("department_code")or"").strip();name=str(p.get("name_zh")or"").strip()
 if not code or not name:raise ValueError("部门代码和中文名称为必填")
 old=db.execute(text("SELECT id FROM tlc_department_master WHERE department_code=:c"),{"c":code}).first();stamp=now();vals={"id":old._mapping["id"] if old else uuid4().hex,"c":code,"z":name,"j":str(p.get("name_ja")or""),"e":str(p.get("name_en")or""),"l":str(p.get("legal_entity_id")or""),"a":1 if p.get("active",True) else 0,"n":stamp}
 db.execute(text("INSERT INTO tlc_department_master VALUES(:id,:c,:z,:j,:e,:l,:a,:n,:n) ON CONFLICT(department_code) DO UPDATE SET name_zh=:z,name_ja=:j,name_en=:e,legal_entity_id=:l,active=:a,updated_at=:n"),vals);audit(db,p.get("actor",""),"DEPARTMENT",code,"SAVE");db.commit();return{"department_code":code}
def save_user(db:Session,p:dict):
 ensure_schema(db)
 emp=str(p.get("employee_no")or"").strip();login=str(p.get("login_id")or"").strip()
 if not emp or not login:raise ValueError("员工编号和登录ID为必填")
 old=db.execute(text("SELECT id,created_at FROM tlc_user_master WHERE employee_no=:e"),{"e":emp}).first();stamp=now();uid=old._mapping["id"] if old else uuid4().hex;created=old._mapping["created_at"] if old else stamp
 vals={"id":uid,"emp":emp,"en":str(p.get("name_en")or""),"ja":str(p.get("name_ja")or""),"zh":str(p.get("name_zh")or""),"email":str(p.get("email")or""),"mobile":str(p.get("mobile")or""),"login":login,"legal":str(p.get("legal_entity_id")or""),"dept":str(p.get("department_id")or""),"active":1 if p.get("active",True) else 0,"vf":str(p.get("valid_from")or""),"vt":str(p.get("valid_to")or""),"created":created,"updated":stamp}
 db.execute(text("INSERT INTO tlc_user_master VALUES(:id,:emp,:en,:ja,:zh,:email,:mobile,:login,:legal,:dept,:active,:vf,:vt,:created,:updated) ON CONFLICT(employee_no) DO UPDATE SET name_en=:en,name_ja=:ja,name_zh=:zh,email=:email,mobile=:mobile,login_id=:login,legal_entity_id=:legal,department_id=:dept,active=:active,valid_from=:vf,valid_to=:vt,updated_at=:updated"),vals);audit(db,p.get("actor",""),"USER",uid,"SAVE");db.commit();return{"id":uid,"employee_no":emp}
def assign_roles(db:Session,user_id:str,role_codes:list[str],actor=""):
 ensure_schema(db)
 if "SUPER_ADMIN" in set(role_codes):raise ValueError("超级管理员只能在超级管理员设置页面授予或撤销")
 db.execute(text("DELETE FROM tlc_user_role WHERE user_id=:u AND role_code<>'SUPER_ADMIN'"),{"u":user_id})
 for role in sorted(set(role_codes)):db.execute(text("INSERT INTO tlc_user_role VALUES(:id,:u,:r,:c,:a)"),{"id":uuid4().hex,"u":user_id,"r":role,"c":now(),"a":actor})
 audit(db,actor,"USER_ROLE",user_id,"REPLACE",",".join(role_codes));db.commit();return{"user_id":user_id,"role_codes":role_codes}
def save_permissions(db:Session,role_code:str,items:list[dict],actor=""):
 ensure_schema(db)
 if role_code=="SUPER_ADMIN":raise ValueError("SUPER_ADMIN固定拥有全部权限，不能从矩阵减少")
 db.execute(text("DELETE FROM tlc_role_permission WHERE role_code=:r"),{"r":role_code});stamp=now()
 for x in items:
  action=str(x.get("action_code")or"");scope=str(x.get("data_scope")or"LEGAL_ENTITY")
  if action not in ACTIONS or scope not in SCOPES:raise ValueError("权限动作或数据范围不正确")
  db.execute(text("INSERT INTO tlc_role_permission VALUES(:id,:r,:m,:a,:s,1,:u,:by)"),{"id":uuid4().hex,"r":role_code,"m":str(x.get("module_code")or""),"a":action,"s":scope,"u":stamp,"by":actor})
 audit(db,actor,"ROLE_PERMISSION",role_code,"REPLACE",str(len(items)));db.commit();return{"role_code":role_code,"count":len(items)}
def audit_rows(db:Session,limit=200):ensure_schema(db);return[dict(x._mapping) for x in db.execute(text("SELECT * FROM tlc_permission_audit ORDER BY id DESC LIMIT :n"),{"n":min(max(int(limit),1),1000)}).all()]

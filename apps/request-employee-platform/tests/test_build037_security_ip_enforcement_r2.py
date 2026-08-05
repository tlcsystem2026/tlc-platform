from datetime import datetime,timedelta,timezone
from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker
from src.services.tlc_access_control_service import ensure_schema as ensure_access
from src.services.tlc_security_ip_control_service import confirm_enforcement,enforce_request,enforcement_status,start_enforcement_test

def db(tmp_path):return sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'enforce.sqlite3'}"))()
def session():return {"user_id":"ROOT","legal_entity_id":"LE","department_id":"D"}
def allow(db,network="10.0.0.0/24"):
 from src.services.tlc_security_ip_control_service import save_rule
 save_rule(db,{"name":"admin","network":network,"decision":"ALLOW","scope_type":"GLOBAL"})

def test_default_deny_only_after_test_starts(tmp_path):
 d=db(tmp_path);ensure_access(d)
 assert enforce_request(d,session(),"GET","/dashboard","203.0.113.8")["blocked"] is False
 allow(d);state=start_enforcement_test(d,session(),"10.0.0.8","","START 5 MINUTE TEST")
 assert state["mode"]=="TEST"
 assert enforce_request(d,session(),"GET","/dashboard","203.0.113.8")["decision"]=="DEFAULT_DENY"

def test_deny_priority_and_local_emergency(tmp_path):
 d=db(tmp_path);ensure_access(d);allow(d)
 from src.services.tlc_security_ip_control_service import save_rule
 save_rule(d,{"name":"deny","network":"10.0.0.9","decision":"DENY","scope_type":"GLOBAL"});start_enforcement_test(d,session(),"10.0.0.8","","START 5 MINUTE TEST")
 assert enforce_request(d,session(),"GET","/dashboard","10.0.0.9")["decision"]=="DENY_MATCH"
 emergency=enforce_request(d,session(),"GET","/dashboard","127.0.0.1");assert not emergency["blocked"] and emergency["emergency"]

def test_confirmation_requires_same_test_and_second_phrase(tmp_path):
 d=db(tmp_path);ensure_access(d);allow(d);state=start_enforcement_test(d,session(),"10.0.0.8","","START 5 MINUTE TEST")
 result=confirm_enforcement(d,session(),"10.0.0.8","",state["test_id"],"CONFIRM PERMANENT ENFORCEMENT")
 assert result["mode"]=="ENFORCED" and result["confirmed_by"]=="ROOT"

def test_expired_test_auto_rolls_back(tmp_path):
 d=db(tmp_path);ensure_access(d);allow(d);start_enforcement_test(d,session(),"10.0.0.8","","START 5 MINUTE TEST")
 old=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat();d.execute(text("UPDATE tlc_ip_enforcement_state SET test_expires_at=:old WHERE id=1"),{"old":old});d.commit()
 assert enforcement_status(d)["mode"]=="MONITOR"
 assert d.execute(text("SELECT COUNT(*) FROM tlc_ip_enforcement_audit WHERE event_type='TEST_AUTO_ROLLBACK'")).scalar_one()==1

def test_cannot_start_when_current_remote_ip_would_be_denied(tmp_path):
 d=db(tmp_path);ensure_access(d);allow(d,"10.0.0.0/24")
 try:start_enforcement_test(d,session(),"203.0.113.8","","START 5 MINUTE TEST")
 except ValueError as exc:assert "当前访问IP" in str(exc)
 else:raise AssertionError("unsafe test start was accepted")

def test_authentication_contract_enforces_public_and_authenticated_paths():
 app=Path(__file__).resolve().parents[1];auth=(app/"src/api/routes/tlc_authentication.py").read_text(encoding="utf-8")
 for value in ("TLC_SECURITY_IP_ENFORCEMENT_R2","public_access=enforce_request","ip_access=enforce_request","LOCAL_EMERGENCY_ALLOW","IP access denied"):
  if value=="LOCAL_EMERGENCY_ALLOW":continue
  assert value in auth

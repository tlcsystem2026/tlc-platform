from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker
from src.services.tlc_access_control_service import ensure_schema as ensure_access
from src.services.tlc_security_ip_control_service import monitor_request,overview,save_proxy,save_rule
from src.services.tlc_api_permission_service import requirement_for

def db(tmp_path):return sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'ip.sqlite3'}"))()
def session():return {"user_id":"U1","legal_entity_id":"LE1","department_id":"D1"}

def test_single_ip_and_cidr_are_normalized(tmp_path):
 d=db(tmp_path);ensure_access(d)
 assert save_rule(d,{"name":"one","network":"192.168.1.8","decision":"ALLOW","scope_type":"GLOBAL"})["network"]=="192.168.1.8/32"
 assert save_rule(d,{"name":"cidr","network":"10.0.0.7/24","decision":"DENY","scope_type":"GLOBAL"})["network"]=="10.0.0.0/24"

def test_monitor_records_violation_but_never_blocks(tmp_path):
 d=db(tmp_path);ensure_access(d);save_rule(d,{"name":"office","network":"10.0.0.0/24","decision":"ALLOW","scope_type":"GLOBAL"})
 result=monitor_request(d,session(),"GET","/dashboard","203.0.113.8")
 assert result["would_block"] is True and result["blocked"] is False and result["mode"]=="MONITOR"
 assert d.execute(text("SELECT would_block FROM tlc_ip_access_audit")).scalar_one()==1

def test_deny_has_priority_and_scopes_apply(tmp_path):
 d=db(tmp_path);ensure_access(d);save_rule(d,{"name":"allow","network":"10.0.0.0/24","decision":"ALLOW","scope_type":"LEGAL_ENTITY","scope_id":"LE1"});save_rule(d,{"name":"deny","network":"10.0.0.9","decision":"DENY","scope_type":"USER","scope_id":"U1"})
 assert monitor_request(d,session(),"GET","/dashboard","10.0.0.9")["decision"]=="WOULD_DENY"

def test_forwarded_ip_only_from_trusted_proxy(tmp_path):
 d=db(tmp_path);ensure_access(d);save_proxy(d,{"name":"proxy","network":"127.0.0.1"})
 result=monitor_request(d,session(),"GET","/dashboard","127.0.0.1","198.51.100.7, 127.0.0.1")
 assert result["trusted_proxy"] and result["effective_ip"]=="198.51.100.7"
 result=monitor_request(d,session(),"GET","/dashboard","203.0.113.2","198.51.100.8")
 assert not result["trusted_proxy"] and result["effective_ip"]=="203.0.113.2"

def test_permission_and_source_contracts():
 assert requirement_for("GET","/security-ip-control-center").action_code=="VIEW"
 assert requirement_for("POST","/api/security-ip-control/rules").action_code=="MAINTAIN"
 app=Path(__file__).resolve().parents[1]
 auth=(app/"src/api/routes/tlc_authentication.py").read_text(encoding="utf-8");main=(app/"src/main.py").read_text(encoding="utf-8")
 assert "TLC_SECURITY_IP_CONTROL_R1" in auth and "monitor_request(permission_db" in auth
 assert "tlc_security_ip_control_router" in main

def test_overview_explicitly_reports_monitor_mode(tmp_path):
 d=db(tmp_path);ensure_access(d);assert overview(d)["mode"]=="MONITOR"

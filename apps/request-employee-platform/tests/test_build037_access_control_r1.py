from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.services.tlc_access_control_service import assign_roles,overview,save_department,save_permissions,save_user
def db(tmp_path):return sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'access.db'}"))()
def test_access_control_seed_and_maintenance(tmp_path):
 s=db(tmp_path);save_department(s,{"department_code":"SALES","name_zh":"销售部","actor":"admin"});u=save_user(s,{"employee_no":"E001","login_id":"e001","name_zh":"测试员工","actor":"admin"});assign_roles(s,u["id"],["SALES_OPERATOR","VIEWER"],"admin");save_permissions(s,"VIEWER",[{"module_code":"DASHBOARD","action_code":"VIEW","data_scope":"SELF"}],"admin");o=overview(s);assert any(x["role_code"]=="SUPER_ADMIN" for x in o["roles"]);assert any(x["employee_no"]=="E001" for x in o["users"]);assert len(o["user_roles"])==2
def test_no_foreign_keys_and_entry_contracts():
 from pathlib import Path
 app=Path(__file__).parents[1];service=(app/"src/services/tlc_access_control_service.py").read_text(encoding="utf-8").upper();assert "FOREIGN KEY" not in service
 assert "/access-control-center" in (app/"src/web/static/dashboard.html").read_text(encoding="utf-8")
 assert "/access-control-center" in (app/"src/web/static/system_parameter_center.html").read_text(encoding="utf-8")

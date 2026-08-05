from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_access_control_service import ensure_schema
from src.services.tlc_api_permission_service import authorize, requirement_for


def db(tmp_path):
    return sessionmaker(bind=create_engine(f"sqlite:///{tmp_path / 'permission.sqlite3'}"))()


def seed_user(database, user_id, role, scope="ALL", module="CUSTOMER_MASTER", action="DELETE", grant=True):
    ensure_schema(database)
    database.execute(text("INSERT INTO tlc_user_master VALUES(:id,:emp,'','','','','',:login,'LE01','D01',1,'','',:now,:now)"),
                     {"id":user_id,"emp":user_id,"login":user_id,"now":"2026-08-05T00:00:00+00:00"})
    database.execute(text("INSERT INTO tlc_user_role VALUES(:id,:user,:role,:now,'TEST')"),
                     {"id":user_id+role,"user":user_id,"role":role,"now":"2026-08-05T00:00:00+00:00"})
    if role != "SUPER_ADMIN" and grant:
        database.execute(text("INSERT OR REPLACE INTO tlc_role_permission VALUES(:id,:role,:module,:action,:scope,1,:now,'TEST')"),
                         {"id":user_id+module+action,"role":role,"module":module,"action":action,"scope":scope,"now":"2026-08-05T00:00:00+00:00"})
    database.commit()


def session(user):
    return {"user_id":user,"legal_entity_id":"LE01","department_id":"D01"}


def test_high_risk_route_map_is_exact():
    assert requirement_for("POST","/api/tlc-customers/delete-batch").action_code == "DELETE"
    assert requirement_for("POST","/api/requests/pending-review/bulk-resolve").action_code == "APPROVE"
    assert requirement_for("POST","/api/database-maintenance/full-backup").module_code == "DATABASE_MAINTENANCE"
    assert requirement_for("GET","/api/tlc-customers").__class__ is type(None)


def test_no_permission_is_denied_and_audited(tmp_path):
    database=db(tmp_path);seed_user(database,"u1","VIEWER",grant=False)
    result=authorize(database,session("u1"),"POST","/api/tlc-customers/delete-batch")
    assert result["required"] and not result["allowed"]
    assert database.execute(text("SELECT allowed FROM tlc_api_permission_audit")).scalar_one() == 0


def test_matching_permission_and_scope_are_allowed(tmp_path):
    database=db(tmp_path);seed_user(database,"u2","CUSTOMER_OPERATOR","LEGAL_ENTITY")
    result=authorize(database,session("u2"),"POST","/api/tlc-customers/delete-batch")
    assert result["allowed"] and result["data_scope"] == "LEGAL_ENTITY"


def test_super_admin_has_every_permission(tmp_path):
    database=db(tmp_path);seed_user(database,"root","SUPER_ADMIN")
    for method,path in (("POST","/api/database-maintenance/full-restore"),("DELETE","/api/legal-entities/LE01"),("PUT","/api/tlc-monthly-close/x/signoff")):
        assert authorize(database,session("root"),method,path)["allowed"]


def test_authentication_middleware_contract():
    app=Path(__file__).resolve().parents[1]
    route=(app/"src/api/routes/tlc_authentication.py").read_text(encoding="utf-8")
    for contract in ("TLC_API_PERMISSION_ENFORCEMENT_R1","authorize(permission_db,session,request.method,request.url.path)","permission_db.close()","status_code=403","request.state.permission_scope"):
        assert contract in route

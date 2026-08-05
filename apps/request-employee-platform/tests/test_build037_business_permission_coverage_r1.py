from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.tlc_access_control_service import ensure_schema
from src.services.tlc_api_permission_service import dashboard_permission_script, requirement_for, visible_modules


def database(tmp_path):
    return sessionmaker(bind=create_engine(f"sqlite:///{tmp_path/'coverage.sqlite3'}"))()


def add_user(db,user,role,permissions=()):
    ensure_schema(db);stamp="2026-08-05T00:00:00+00:00"
    db.execute(text("INSERT INTO tlc_user_master VALUES(:id,:id,'','','','','',:id,'LE','DEP',1,'','',:s,:s)"),{"id":user,"s":stamp})
    db.execute(text("INSERT INTO tlc_user_role VALUES(:id,:u,:r,:s,'TEST')"),{"id":user+role,"u":user,"r":role,"s":stamp})
    for index,(module,action) in enumerate(permissions):
        db.execute(text("INSERT OR REPLACE INTO tlc_role_permission VALUES(:id,:r,:m,:a,'ALL',1,:s,'TEST')"),{"id":f"{user}{index}","r":role,"m":module,"a":action,"s":stamp})
    db.commit()


def test_page_and_api_routes_are_covered():
    expected=(("GET","/dashboard","DASHBOARD","VIEW"),("POST","/api/tlc-request-batch-compare-import/run","REQUEST_BATCH","EDIT"),("GET","/requests/review-workbench","REQUEST_BUSINESS_REVIEW","VIEW"),("GET","/sales","SALES_STATISTICS","VIEW"),("POST","/api/bank-import/run","BANK_IMPORT","EDIT"),("GET","/customer-reconciliation-workbench","CUSTOMER_RECONCILIATION","VIEW"),("GET","/operational-exception-dashboard","OPERATIONAL_EXCEPTION","VIEW"),("GET","/guided-monthly-workflow","MONTHLY_WORKFLOW","VIEW"))
    for method,path,module,action in expected:
        result=requirement_for(method,path);assert (result.module_code,result.action_code)==(module,action)


def test_visible_navigation_uses_view_permissions(tmp_path):
    db=database(tmp_path);add_user(db,"u","VIEWER",(("DASHBOARD","VIEW"),("SALES_STATISTICS","VIEW"),("BANK_IMPORT","EDIT")))
    result=visible_modules(db,{"user_id":"u"})
    assert result["modules"]==["DASHBOARD","SALES_STATISTICS"]
    assert result["navigation"]["/sales"]=="SALES_STATISTICS"


def test_super_admin_sees_all_business_modules(tmp_path):
    db=database(tmp_path);add_user(db,"root","SUPER_ADMIN")
    result=visible_modules(db,{"user_id":"root"})
    assert {"DASHBOARD","REQUEST_BATCH","REQUEST_FILE_REVIEW","REQUEST_BUSINESS_REVIEW","SALES_STATISTICS","BANK_IMPORT","CUSTOMER_RECONCILIATION","OPERATIONAL_EXCEPTION","MONTHLY_WORKFLOW","MONTHLY_CLOSE"} <= set(result["modules"])


def test_dashboard_filter_contract():
    script=dashboard_permission_script()
    assert "TLC_BUSINESS_PERMISSION_COVERAGE_R1" in script
    assert "/api/auth/navigation" in script and "allowed.has" in script


def test_authentication_integration_contract():
    app=Path(__file__).resolve().parents[1]
    auth=(app/"src/api/routes/tlc_authentication.py").read_text(encoding="utf-8")
    for value in ("TLC_BUSINESS_PERMISSION_COVERAGE_R1","/api/auth/navigation","visible_modules","dashboard_permission_script","body_iterator"):
        assert value in auth

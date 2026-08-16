import base64
from pathlib import Path


ROOT = Path(__file__).parents[1]
PAGE = ROOT / "src/web/static/dashboard.html"
FLOW = base64.b64decode("5Lia5Yqh5rWB56iL5LiO5rWL6K+V5YWl5Y+j").decode()
SECURITY = base64.b64decode("5Lq65ZGY44CB5p2D6ZmQ5LiO5a6J5YWo566h55CG").decode()
OPERATIONS = base64.b64decode("57O757uf6L+Q57u0").decode()
TODO = base64.b64decode("5LuK5pel5Lia5YqhVE9ETw==").decode()


def test_dashboard_primary_modules_are_directly_below_header():
    page = PAGE.read_text(encoding="utf-8-sig")
    workflow = page.index(FLOW)
    security = page.index(SECURITY)
    operations = page.index(OPERATIONS)
    todo = page.index(TODO)
    assert workflow < security < operations < todo
    assert page.count(FLOW) == 1
    assert page.count(SECURITY) == 1
    assert page.count("<h2>" + OPERATIONS + "</h2>") == 1


def test_dashboard_keeps_current_customer_name_route():
    page = PAGE.read_text(encoding="utf-8-sig")
    assert "/customer-name-matching-center" in page
    assert "/customer-name-identity-center" in page
    assert "/customer-identity-audit-center" in page


def test_dashboard_top_modules_precede_dynamic_business_content():
    page = PAGE.read_text(encoding="utf-8-sig")
    operations_section = page.index('id="system-operations"')
    kpi_section = page.index('id="kpis"')
    digital_employees = page.index('id="digital-employees"')
    assert operations_section < kpi_section < digital_employees

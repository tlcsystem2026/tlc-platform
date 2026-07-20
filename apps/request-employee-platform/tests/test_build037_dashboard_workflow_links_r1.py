from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_dashboard_has_complete_business_workflow_links():
    response = client.get("/dashboard")
    assert response.status_code == 200
    html = response.text
    assert "BUILD037_DASHBOARD_BUSINESS_WORKFLOW_LINKS_R1" in html
    assert "业务流程与测试入口" in html
    expected = [
        "/tlc-customer-master",
        "/tlc-bank-account-master",
        "/request-review-center",
        "/requests/review-workbench",
        "/sales",
        "/sales-ledger-evidence-center",
        "/bank-import",
        "/customer-alias-matching-center",
        "/customer-auto-matching-center",
        "/customer-recommended-matching-center",
        "/customer-payment-reconciliation",
        "/customer-reconciliation-workbench",
        "/customer-payment-reconciliation/confirm",
        "/operational-exception-dashboard",
        "/guided-monthly-workflow",
        "/monthly-close-center",
    ]
    for href in expected:
        assert f'href="{href}"' in html

def test_dashboard_workflow_order_is_visible():
    html = client.get("/dashboard").text
    assert html.index("① 基础主数据") < html.index("② 请求书与正式销售")
    assert html.index("② 请求书与正式销售") < html.index("③ 银行入金与客户匹配")
    assert html.index("③ 银行入金与客户匹配") < html.index("④ 客户对账与确认")
    assert html.index("④ 客户对账与确认") < html.index("⑤ 异常、月度流程与月结")

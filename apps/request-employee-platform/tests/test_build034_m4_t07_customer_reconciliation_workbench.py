from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_customer_reconciliation_workbench_page_available():
    response = client.get("/customer-reconciliation-workbench")

    assert response.status_code == 200
    html = response.text
    assert "客户对账工作台" in html
    assert "/api/tlc-customers" in html
    assert "/api/customer-bank-matching/run" in html
    assert "/api/customer-payment-reconciliation/latest" in html
    assert "/api/customer-payment-reconciliation/calculate" in html
    assert "/api/customer-payment-reconciliation/confirm" in html
    assert "/api/customer-payment-reconciliation/history" in html
    assert "/tlc-customer-master" in html
    assert "/bank-import" in html
    assert "/requests/review-workbench" in html
    assert "未匹配 / 歧义银行流水" in html


def test_workbench_keeps_one_screen_business_flow():
    response = client.get("/customer-reconciliation-workbench")
    html = response.text

    assert "执行银行客户匹配" in html
    assert "计算对账" in html
    assert "确认并保存" in html
    assert "销售明细" in html
    assert "入金明细" in html
    assert "对账历史" in html

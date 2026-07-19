from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_step06_legacy_contract_tokens_remain_present():
    response = client.get("/tlc-bank-account-master")
    assert response.status_code == 200
    html = response.text

    for required in [
        "BUILD037_STEP06_BANK_PAGE",
        "银行 Master",
        "银行账户／口座与流水格式关联",
        "CSV模板",
        "CSV导出",
        "CSV导入",
        "/api/tlc-bank-accounts/template.csv",
        "/api/tlc-bank-accounts/export.csv",
        "/api/tlc-bank-accounts/import",
    ]:
        assert required in html

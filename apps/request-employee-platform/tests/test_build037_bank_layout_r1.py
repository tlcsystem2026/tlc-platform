from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_build037_bank_page_top_middle_bottom_layout():
    response = client.get("/tlc-bank-account-master")
    assert response.status_code == 200
    html = response.text

    assert "BUILD037_STEP06_BANK_PAGE" in html

    assert html.index("单个银行维护") < html.index("银行检索条件")
    assert html.index("银行检索条件") < html.index("银行一览（全部字段）")

    assert html.index("单个银行账户／口座维护") < html.index(
        "账户检索条件／CSV 导入导出"
    )
    assert html.index("账户检索条件／CSV 导入导出") < html.index(
        "银行账户一览（全部字段）"
    )

    for required in [
        "bankRows",
        "accountRows",
        "bankFilterCode",
        "bankFilterName",
        "filterBranchCode",
        "filterBranchName",
        "filterAccountHolder",
        "filterAdapterCode",
        "bank-row-check",
        "account-row-check",
        "created_at",
        "updated_at",
    ]:
        assert required in html


def test_build037_bank_page_all_fields_are_visible():
    html = client.get("/tlc-bank-account-master").text

    for bank_field in [
        "id",
        "category_code",
        "code",
        "name_zh",
        "name_ja",
        "name_en",
        "sort_order",
        "active",
        "extra_json",
        "created_at",
        "updated_at",
    ]:
        assert bank_field in html

    for account_field in [
        "id",
        "bank_code",
        "branch_code",
        "branch_name",
        "account_type",
        "account_number",
        "account_holder",
        "adapter_code",
        "file_encoding",
        "active",
        "note",
        "created_at",
        "updated_at",
    ]:
        assert account_field in html

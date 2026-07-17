from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_build037_step06_page_contract():
    response = client.get("/tlc-bank-account-master")
    assert response.status_code == 200
    html = response.text
    assert "BUILD037_STEP06_BANK_PAGE" in html
    assert "银行 Master" in html
    assert "银行账户／口座与流水格式关联" in html
    assert "/api/tlc-bank-accounts/import" in html
    assert "/api/tlc-bank-accounts/export.csv" in html


def test_build037_step06_bank_master_and_account():
    suffix = uuid4().hex[:10]
    bank_code = f"STEP06_BANK_{suffix}".upper()
    bank = client.post(
        "/api/tlc-codes/values",
        json={
            "category_code": "BANK",
            "code": bank_code,
            "name_zh": f"测试银行 {suffix}",
            "name_ja": "",
            "name_en": "",
            "sort_order": 900,
            "active": True,
            "extra_json": {},
        },
    )
    assert bank.status_code == 200

    account_number = f"STEP06-{suffix}"
    account = client.post(
        "/api/tlc-bank-accounts",
        json={
            "bank_code": bank_code,
            "account_number": account_number,
            "adapter_code": f"ADAPTER_{suffix}",
            "file_encoding": "utf-8",
            "active": True,
        },
    )
    assert account.status_code == 200
    assert account.json()["adapter_code"] == f"ADAPTER_{suffix}"


def test_build037_step06_import_is_atomic_on_error():
    suffix = uuid4().hex[:10]
    good_number = f"STEP06-ATOMIC-{suffix}"
    response = client.post(
        "/api/tlc-bank-accounts/import",
        json={
            "rows": [
                {
                    "bank_code": "SUGAMO_SHINKIN",
                    "account_number": good_number,
                    "adapter_code": "STEP06_TEST",
                },
                {
                    "bank_code": "UNKNOWN_BANK",
                    "account_number": f"STEP06-BAD-{suffix}",
                },
            ]
        },
    )
    assert response.status_code == 400
    lookup = client.get(
        "/api/tlc-bank-accounts",
        params={"account_number": good_number},
    )
    assert lookup.status_code == 200
    assert not any(
        row["account_number"] == good_number for row in lookup.json()
    )


def test_build037_step06_template_and_export():
    template = client.get("/api/tlc-bank-accounts/template.csv")
    assert template.status_code == 200
    assert "bank_code" in template.text
    assert "adapter_code" in template.text

    exported = client.get("/api/tlc-bank-accounts/export.csv")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "file_encoding" in exported.text


def test_build037_step06_dashboard_entry():
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    paths = [item["href"] for item in response.json()["navigator"]]
    assert "/tlc-bank-account-master" in paths
    assert "/tlc-customer-master" in paths
    assert "/request-review-center" in [
        item["href"] for item in response.json()["todos"]
    ]

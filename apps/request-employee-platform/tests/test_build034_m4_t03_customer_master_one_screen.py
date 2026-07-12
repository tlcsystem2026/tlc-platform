from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app
from src.services.tlc_customer_master_service import normalize_customer_name


client = TestClient(app)


def test_customer_master_page_available():
    response = client.get("/tlc-customer-master")
    assert response.status_code == 200
    assert "客户档案" in response.text
    assert "/api/tlc-customers" in response.text
    assert "alias_5" in response.text or "别名5" in response.text
    assert "/tlc-code-master" in response.text


def test_customer_create_update_search_and_aliases():
    suffix = uuid4().hex[:10]
    customer_id = f"CUST-{suffix}"
    formal_name = f"株式会社テスト商事{suffix}"
    hiragana_name = f"てすとしょうじ{suffix}"
    katakana_name = f"テストショウジ{suffix}"
    short_name = f"テスト{suffix}"
    alias_1 = f"TEST SHOJI {suffix}"
    alias_2 = f"テスト商事{suffix}"

    created = client.post("/api/tlc-customers", json={
        "customer_id": customer_id,
        "formal_name": formal_name,
        "hiragana_name": hiragana_name,
        "katakana_name": katakana_name,
        "short_name": short_name,
        "alias_1": alias_1,
        "alias_2": alias_2,
        "status_code": "ACTIVE",
        "active": True,
    })
    assert created.status_code == 200, created.text
    record = created.json()
    assert record["customer_id"] == customer_id
    assert alias_1 in record["aliases"]

    alias_3 = f"TLC TEST CUSTOMER {suffix}"
    updated = client.post("/api/tlc-customers", json={
        **record,
        "alias_3": alias_3,
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["alias_3"] == alias_3

    search = client.get("/api/tlc-customers", params={"query": alias_1})
    assert search.status_code == 200
    assert any(row["customer_id"] == customer_id for row in search.json())


def test_customer_id_and_alias_conflicts_are_rejected():
    suffix = uuid4().hex[:8]
    first = client.post("/api/tlc-customers", json={
        "customer_id": f"CUST-A-{suffix}",
        "formal_name": f"株式会社重複テスト{suffix}",
        "alias_1": f"DUPLICATE-{suffix}",
    })
    assert first.status_code == 200

    duplicate_id = client.post("/api/tlc-customers", json={
        "customer_id": f"CUST-A-{suffix}",
        "formal_name": f"別会社{suffix}",
    })
    assert duplicate_id.status_code == 400

    duplicate_alias = client.post("/api/tlc-customers", json={
        "customer_id": f"CUST-B-{suffix}",
        "formal_name": f"別会社B{suffix}",
        "alias_2": f"DUPLICATE-{suffix}",
    })
    assert duplicate_alias.status_code == 400


def test_name_normalization_handles_width_spaces_and_company_suffix():
    assert normalize_customer_name(" 株式会社 ＴＥＳＴ　商事 ") == "test商事"

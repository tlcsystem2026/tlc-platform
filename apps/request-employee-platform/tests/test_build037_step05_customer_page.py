from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_build037_step05_customer_page_contract():
    page = client.get("/tlc-customer-master")
    assert page.status_code == 200
    for required in [
        "BUILD037_STEP05_CUSTOMER_PAGE",
        "客户维护",
        "CSV 导入",
        "CSV 导出",
        "别名5",
        "/api/tlc-customers/import",
        "/api/tlc-customers/export.csv",
    ]:
        assert required in page.text


def test_build037_step05_dashboard_entry():
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    navigation = response.json()["navigator"]
    target = [item for item in navigation if item["title"] == "客户跟踪与分析"]
    assert len(target) == 1
    assert target[0]["href"] == "/tlc-customer-master"


def test_build037_step05_customer_import_export_upsert():
    suffix = uuid4().hex[:10]
    customer_id = f"STEP05-{suffix}"

    imported = client.post("/api/tlc-customers/import", json={"rows": [{
        "customer_id": customer_id,
        "formal_name": f"株式会社Step05{suffix}",
        "alias_1": f"STEP05 ALIAS {suffix}",
        "status_code": "ACTIVE",
        "active": "1",
    }]})
    assert imported.status_code == 200, imported.text
    assert imported.json() == {"imported": 1, "created": 1, "updated": 0}

    updated = client.post("/api/tlc-customers/import", json={"rows": [{
        "customer_id": customer_id,
        "formal_name": f"株式会社Step05{suffix}",
        "alias_1": f"STEP05 ALIAS {suffix}",
        "alias_2": f"STEP05 SECOND {suffix}",
        "status_code": "ACTIVE",
        "active": "1",
    }]})
    assert updated.status_code == 200, updated.text
    assert updated.json() == {"imported": 1, "created": 0, "updated": 1}

    exported = client.get("/api/tlc-customers/export.csv", params={"query": customer_id})
    assert exported.status_code == 200
    assert "text/csv" in exported.headers["content-type"]
    assert customer_id in exported.text
    assert f"STEP05 SECOND {suffix}" in exported.text


def test_build037_step05_import_is_atomic_on_error():
    suffix = uuid4().hex[:10]
    good_id = f"STEP05-ATOMIC-{suffix}"
    response = client.post("/api/tlc-customers/import", json={"rows": [
        {"customer_id": good_id, "formal_name": f"Atomic Good {suffix}"},
        {"customer_id": f"STEP05-BAD-{suffix}", "formal_name": ""},
    ]})
    assert response.status_code == 400
    lookup = client.get("/api/tlc-customers", params={"query": good_id})
    assert lookup.status_code == 200
    assert not any(row["customer_id"] == good_id for row in lookup.json())

from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_legacy_json_import_and_upsert():
    suffix = uuid4().hex[:10]
    customer_id = f"R3-{suffix}"

    created = client.post("/api/tlc-customers/import", json={"rows": [{
        "customer_id": customer_id,
        "formal_name": f"株式会社R3{suffix}",
        "alias_1": f"R3 ALIAS {suffix}",
        "status_code": "ACTIVE",
        "active": "1",
    }]})
    assert created.status_code == 200, created.text
    assert created.json() == {"imported": 1, "created": 1, "updated": 0}

    updated = client.post("/api/tlc-customers/import", json={"rows": [{
        "customer_id": customer_id,
        "formal_name": f"株式会社R3更新{suffix}",
        "alias_1": f"R3 UPDATED {suffix}",
        "status_code": "ACTIVE",
        "active": "1",
    }]})
    assert updated.status_code == 200, updated.text
    assert updated.json() == {"imported": 1, "created": 0, "updated": 1}


def test_legacy_json_import_is_atomic_on_validation_error():
    suffix = uuid4().hex[:10]
    good_id = f"R3-ATOMIC-{suffix}"

    response = client.post("/api/tlc-customers/import", json={"rows": [
        {"customer_id": good_id, "formal_name": f"Atomic Good {suffix}"},
        {"customer_id": f"R3-BAD-{suffix}", "formal_name": ""},
    ]})
    assert response.status_code == 400

    lookup = client.get("/api/tlc-customers", params={"customer_id": good_id})
    assert lookup.status_code == 200
    assert lookup.json() == []

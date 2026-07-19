from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_legacy_json_import_response_contract_is_exact():
    suffix = uuid4().hex[:10]
    customer_id = f"R4-{suffix}"

    created = client.post(
        "/api/tlc-customers/import",
        json={
            "rows": [
                {
                    "customer_id": customer_id,
                    "formal_name": f"株式会社R4{suffix}",
                    "alias_1": f"R4 ALIAS {suffix}",
                    "status_code": "ACTIVE",
                    "active": "1",
                }
            ]
        },
    )
    assert created.status_code == 200, created.text
    assert created.json() == {
        "imported": 1,
        "created": 1,
        "updated": 0,
    }

    updated = client.post(
        "/api/tlc-customers/import",
        json={
            "rows": [
                {
                    "customer_id": customer_id,
                    "formal_name": f"株式会社R4更新{suffix}",
                    "alias_1": f"R4 UPDATED {suffix}",
                    "status_code": "ACTIVE",
                    "active": "1",
                }
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json() == {
        "imported": 1,
        "created": 0,
        "updated": 1,
    }

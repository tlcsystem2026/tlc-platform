
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _create_customer():
    customer_id = f"CUST-{uuid4().hex[:10]}"
    response = client.post("/api/tlc-customers", json={
        "customer_id": customer_id,
        "formal_name": f"株式会社ABC商事{uuid4().hex[:4]}",
        "hiragana_name": "えーびーしーしょうじ",
        "katakana_name": "エービーシーショウジ",
        "short_name": "ABC",
        "alias_1": "ABC SHOUJI",
        "alias_2": "ＡＢＣ・商事",
        "status_code": "ACTIVE",
        "active": True,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_exact_alias_and_normalization_match():
    customer = _create_customer()

    response = client.post(
        "/api/tlc-customer-alias-matching/match",
        json={
            "raw_name": " ＡＢＣ・商事（株） ",
            "operator": "tester",
            "save_result": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["match_status"] == "MATCHED"
    assert body["customer_id"] == customer["customer_id"]
    assert body["match_level"] in {
        "EXACT",
        "ALIAS",
        "SHORT_NAME",
        "KATAKANA",
        "HIRAGANA",
    }


def test_unmatched_name_returns_unmatched():
    response = client.post(
        "/api/tlc-customer-alias-matching/match",
        json={
            "raw_name": f"NO_MATCH_{uuid4().hex}",
            "operator": "tester",
        },
    )
    assert response.status_code == 200
    assert response.json()["match_status"] == "UNMATCHED"


def test_page_available_and_connected():
    response = client.get("/customer-alias-matching-center")
    assert response.status_code == 200
    html = response.text
    assert "Customer Alias Matching Center" in html
    assert "/api/tlc-customer-alias-matching/match" in html
    assert 'href="/customer-reconciliation-period-center"' in html
    assert 'href="/business-operations-home"' in html

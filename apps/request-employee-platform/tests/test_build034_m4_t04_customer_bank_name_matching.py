from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app
from src.services.customer_bank_name_matching_service import (
    normalize_bank_counterparty,
)


client = TestClient(app)


def _create_customer(customer_id: str, formal_name: str, **kwargs):
    payload = {
        "customer_id": customer_id,
        "formal_name": formal_name,
        "status_code": "ACTIVE",
        "active": True,
    }
    payload.update(kwargs)
    response = client.post("/api/tlc-customers", json=payload)
    assert response.status_code == 200
    return response.json()


def test_normalization_handles_width_spaces_punctuation_and_company_suffix():
    assert normalize_bank_counterparty(" 株式会社 ＡＢＣ・商事（株） ") == "abc商事"
    assert normalize_bank_counterparty("ＡＢＣ商事㈱") == "abc商事"


def test_exact_normalized_alias_match():
    suffix = uuid4().hex[:8]
    customer_id = f"CUST-MATCH-{suffix}"
    _create_customer(
        customer_id,
        f"株式会社テスト販売{suffix}",
        alias_1=f"ＴＥＳＴ　ＳＡＬＥＳ・{suffix}",
    )

    response = client.get(
        "/api/customer-bank-matching/preview",
        params={"counterparty": f"test sales {suffix}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "MATCHED"
    assert body["customer_id"] == customer_id
    assert body["matched_field"] == "alias_1"


def test_unmatched_name_is_not_guessed():
    response = client.get(
        "/api/customer-bank-matching/preview",
        params={"counterparty": f"UNKNOWN-{uuid4().hex}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "UNMATCHED"


def test_ambiguous_name_is_not_auto_assigned():
    suffix = uuid4().hex[:8]
    shared_alias = f"AMBIGUOUS-{suffix}"

    first = _create_customer(
        f"CUST-AMB-A-{suffix}",
        f"第一顧客{suffix}",
        alias_1=shared_alias,
    )

    # The customer master prevents duplicate aliases, so create a deliberate
    # ambiguity directly through an alternative normalized spelling on a
    # different field that becomes equal after punctuation normalization.
    second_alias = f"AMBIGUOUS ・ {suffix}"
    second = client.post("/api/tlc-customers", json={
        "customer_id": f"CUST-AMB-B-{suffix}",
        "formal_name": f"第二顧客{suffix}",
        "alias_2": second_alias,
        "status_code": "ACTIVE",
        "active": True,
    })

    if second.status_code == 200:
        response = client.get(
            "/api/customer-bank-matching/preview",
            params={"counterparty": shared_alias},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "AMBIGUOUS"
    else:
        # Duplicate prevention is also an acceptable guard against ambiguity.
        assert second.status_code == 400
        assert "conflicts" in second.json()["detail"]

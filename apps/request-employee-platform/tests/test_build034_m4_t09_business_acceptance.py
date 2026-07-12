from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _create_customer(customer_id: str, alias: str) -> None:
    response = client.post("/api/tlc-customers", json={
        "customer_id": customer_id,
        "formal_name": f"株式会社{alias}",
        "alias_1": alias,
        "status_code": "ACTIVE",
        "active": True,
    })
    assert response.status_code == 200, response.text


def _create_sales_request(
    customer_id: str,
    request_no: str,
    request_date: str,
    amount: str,
) -> str:
    pending = client.post("/api/requests/pending-review", json={
        "matched": True,
        "request_no": request_no,
        "difference_count": 0,
        "sources": {
            "excel": request_no + ".xlsx",
            "pdf": request_no + ".pdf",
        },
        "request_document": {
            "request_no": request_no,
            "request_date": request_date,
            "customer_id": customer_id,
            "customer_name": "Acceptance Customer",
            "currency": "JPY",
            "subtotal": amount,
            "tax_amount": "0",
            "total_amount": amount,
        },
    })
    assert pending.status_code == 200, pending.text
    record_id = pending.json()["record"]["id"]

    approved = client.post(
        f"/api/requests/pending-review/{record_id}/resolve",
        json={
            "action": "APPROVE",
            "reviewed_by": "acceptance-user",
            "note": "Build034 milestone acceptance",
        },
    )
    assert approved.status_code == 200, approved.text

    posted = client.post(
        f"/api/sales-ledger/from-pending-review/{record_id}"
    )
    assert posted.status_code == 200, posted.text
    return posted.json()["ledger"]["id"]


def _import_bank_credit(
    counterparty: str,
    transaction_id: str,
    transaction_date: str,
    amount: str,
) -> None:
    csv_body = f"""お客さま口座情報
お客さま口座番号：10190-ACCEPTANCE
取引日,入出金明細ＩＤ,受入金額（円）,払出金額（円）,詳細１,詳細２,現在（貸付）高,
{transaction_date.replace("-", "")},{transaction_id},{amount},,送金,{counterparty},999999,
""".encode("cp932")

    imported = client.post(
        f"/api/bank-import/csv?source_name={transaction_id}.csv",
        content=csv_body,
        headers={"content-type": "text/csv"},
    )
    assert imported.status_code == 200, imported.text


def test_build034_end_to_end_business_acceptance():
    suffix = uuid4().hex[:10]
    customer_id = f"CUST-ACCEPT-{suffix}"
    alias = f"ACCEPTANCE PAYER {suffix}"

    _create_customer(customer_id, alias)

    ledger_id = _create_sales_request(
        customer_id,
        f"REQ-ACCEPT-{suffix}",
        "2026-07-10",
        "1000",
    )

    _import_bank_credit(
        alias,
        f"TX-ACCEPT-{suffix}",
        "2026-07-20",
        "600",
    )

    matched = client.post(
        "/api/customer-bank-matching/run",
        params={"limit": 1000},
    )
    assert matched.status_code == 200, matched.text
    assert matched.json()["matched"] >= 1

    calculated = client.get(
        "/api/customer-payment-reconciliation/calculate",
        params={
            "customer_id": customer_id,
            "previous_request_cutoff": "2026-06-30",
            "current_request_cutoff": "2026-07-31",
            "previous_bank_cutoff": "2026-06-30",
            "current_bank_cutoff": "2026-07-31",
            "opening_outstanding": "200",
        },
    )
    assert calculated.status_code == 200, calculated.text
    body = calculated.json()

    assert body["sales_total"] == "1000"
    assert body["payment_total"] == "600"
    assert body["opening_outstanding"] == "200"
    assert body["closing_outstanding"] == "600"
    assert body["status"] == "PARTIAL"
    assert any(row["id"] == ledger_id for row in body["sales"])

    confirmed = client.post(
        "/api/customer-payment-reconciliation/confirm",
        json={
            "customer_id": customer_id,
            "previous_request_cutoff": "2026-06-30",
            "current_request_cutoff": "2026-07-31",
            "previous_bank_cutoff": "2026-06-30",
            "current_bank_cutoff": "2026-07-31",
            "opening_outstanding": "200",
            "confirmed_by": "acceptance-user",
            "note": "Build034 end-to-end acceptance",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "saved"
    assert confirmed.json()["record"]["closing_outstanding"] == "600"

    latest = client.get(
        "/api/customer-payment-reconciliation/latest",
        params={"customer_id": customer_id},
    )
    assert latest.status_code == 200, latest.text
    assert latest.json()["closing_outstanding"] == "600"

    carry_forward = client.get(
        "/api/customer-payment-reconciliation/calculate",
        params={
            "customer_id": customer_id,
            "previous_request_cutoff": "2026-07-31",
            "current_request_cutoff": "2026-08-31",
            "previous_bank_cutoff": "2026-07-31",
            "current_bank_cutoff": "2026-08-31",
        },
    )
    assert carry_forward.status_code == 200, carry_forward.text
    assert carry_forward.json()["opening_outstanding"] == "600"


def test_build034_primary_business_pages_are_available():
    pages = {
        "/requests/review-workbench": "销售请求书审核工作台",
        "/bank-import": "银行流水导入与查看",
        "/tlc-code-master": "TLC Code Master",
        "/tlc-bank-account-master": "银行账户与导入配置",
        "/tlc-customer-master": "客户档案",
        "/customer-reconciliation-workbench": "客户对账工作台",
    }

    for path, marker in pages.items():
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.text}"
        assert marker in response.text

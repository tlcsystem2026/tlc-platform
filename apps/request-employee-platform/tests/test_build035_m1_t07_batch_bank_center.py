from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app

client=TestClient(app)

def make_batch():
    b=client.post("/api/tlc-batches",json={"business_month":"2027-04","title":uuid4().hex,"created_by":"tester"}).json()
    for s in ["IMPORTING","COMPARE","READY_REVIEW","REVIEWING","LEDGER_POSTED"]:
        r=client.post(f"/api/tlc-batches/{b["id"]}/transition",json={"new_status":s,"operator":"tester"})
        assert r.status_code==200,r.text
    return b

def test_link_moves_to_bank_imported():
    b=make_batch()
    r=client.post(f"/api/tlc-batches/{b["id"]}/bank/links",json={
      "bank_transaction_id":"BANK-"+uuid4().hex,"transaction_id":"TX-"+uuid4().hex[:8],
      "transaction_date":"2027-04-10","direction":"CREDIT","amount":"1200",
      "counterparty":"TEST","linked_by":"tester"})
    assert r.status_code==200,r.text
    assert client.get(f"/api/tlc-batches/{b["id"]}").json()["status"]=="BANK_IMPORTED"

def test_idempotent_and_summary():
    b=make_batch();rid="BANK-"+uuid4().hex
    payload={"bank_transaction_id":rid,"direction":"CREDIT","amount":"500","linked_by":"tester"}
    a=client.post(f"/api/tlc-batches/{b["id"]}/bank/links",json=payload)
    z=client.post(f"/api/tlc-batches/{b["id"]}/bank/links",json=payload)
    assert a.status_code==200 and z.status_code==200
    assert z.json()["status"]=="exists"
    s=client.get(f"/api/tlc-batches/{b["id"]}/bank/summary").json()
    assert s["transaction_count"]==1 and s["credit_total"]=="500"

def test_page_connected():
    html=client.get("/batch-center").text
    assert "/bank/links" in html and "/bank/summary" in html
    assert "登记银行流水" in html and 'name==="bank"' in html

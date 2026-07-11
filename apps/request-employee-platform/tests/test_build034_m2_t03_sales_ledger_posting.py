from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app
client=TestClient(app)

def create_pending():
    no="REQ-M2T03-"+uuid4().hex[:12]
    payload={"matched":True,"request_no":no,"difference_count":0,
      "sources":{"excel":no+".xlsx","pdf":no+".pdf"},
      "request_document":{"request_no":no,"request_date":"2026-07-10","customer_id":"CUST-LEDGER",
      "customer_name":"Ledger Customer","currency":"JPY","subtotal":"1000","tax_amount":"100","total_amount":"1100"}}
    r=client.post("/api/requests/pending-review",json=payload); assert r.status_code==200
    return r.json()["record"]

def approve(rid):
    r=client.post(f"/api/requests/pending-review/{rid}/resolve",json={"action":"APPROVE","reviewed_by":"reviewer","note":"ok"})
    assert r.status_code==200

def test_only_approved_can_post():
    rec=create_pending()
    assert client.post(f"/api/sales-ledger/from-pending-review/{rec['id']}").status_code==400
    approve(rec["id"])
    r=client.post(f"/api/sales-ledger/from-pending-review/{rec['id']}")
    assert r.status_code==200
    body=r.json(); assert body["status"]=="posted"; assert body["ledger"]["request_no"]==rec["request_no"]

def test_posting_idempotent_and_list_detail():
    rec=create_pending(); approve(rec["id"])
    a=client.post(f"/api/sales-ledger/from-pending-review/{rec['id']}").json()
    b=client.post(f"/api/sales-ledger/from-pending-review/{rec['id']}").json()
    assert a["status"]=="posted" and b["status"]=="exists"
    lid=a["ledger"]["id"]; assert lid==b["ledger"]["id"]
    rows=client.get("/api/sales-ledger",params={"customer_id":"CUST-LEDGER"}).json()
    assert any(x["id"]==lid for x in rows)
    assert client.get(f"/api/sales-ledger/{lid}").json()["pending_review_id"]==rec["id"]

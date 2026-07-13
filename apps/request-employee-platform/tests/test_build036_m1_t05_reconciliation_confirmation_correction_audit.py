
from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app
client=TestClient(app)

def snapshot():
    r=client.post("/api/tlc-customer-reconciliation-snapshots/calculate",json={
      "customer_id":f"C-{uuid4().hex[:10]}","customer_name":"Confirmation Test",
      "previous_request_cutoff":"2026-01-31","current_request_cutoff":"2026-02-28",
      "previous_bank_cutoff":"2026-01-31","current_bank_cutoff":"2026-02-28","created_by":"tester"})
    assert r.status_code==200,r.text
    return r.json()

def test_create_correct_confirm_reopen_audit():
    s=snapshot()
    c=client.post("/api/tlc-customer-reconciliation-confirmations",json={"snapshot_id":s["id"],"operator":"tester"})
    assert c.status_code==200,c.text
    rec=c.json()["confirmation"];assert rec["status"]=="DRAFT"
    corrected=client.put(f"/api/tlc-customer-reconciliation-confirmations/{rec['id']}",json={
      "status":"CORRECTED","operator":"tester","confirmed_sales_total":"1000",
      "confirmed_payment_total":"400","correction_reason":"Manual correction"})
    assert corrected.status_code==200,corrected.text
    assert corrected.json()["confirmed_unpaid_amount"]=="600"
    confirmed=client.put(f"/api/tlc-customer-reconciliation-confirmations/{rec['id']}",json={"status":"CONFIRMED","operator":"manager"})
    assert confirmed.status_code==200 and confirmed.json()["status"]=="CONFIRMED"
    reopened=client.put(f"/api/tlc-customer-reconciliation-confirmations/{rec['id']}",json={"status":"REOPENED","operator":"manager"})
    assert reopened.status_code==200 and reopened.json()["status"]=="REOPENED"
    audit=client.get("/api/tlc-customer-reconciliation-confirmations/audit",params={"confirmation_id":rec["id"]})
    assert audit.status_code==200 and len(audit.json())>=4

def test_correction_requires_reason():
    s=snapshot();rec=client.post("/api/tlc-customer-reconciliation-confirmations",json={"snapshot_id":s["id"],"operator":"tester"}).json()["confirmation"]
    r=client.put(f"/api/tlc-customer-reconciliation-confirmations/{rec['id']}",json={
      "status":"CORRECTED","operator":"tester","confirmed_sales_total":"100","confirmed_payment_total":"50"})
    assert r.status_code==400
    assert "correction_reason is required" in r.json()["detail"]

def test_page():
    h=client.get("/customer-reconciliation-confirmation-center").text
    assert "Customer Reconciliation Confirmation Center" in h
    assert "/api/tlc-customer-reconciliation-confirmations" in h
    assert 'href="/sales-ledger-evidence-center"' in h
    assert 'href="/bank-payment-evidence-center"' in h

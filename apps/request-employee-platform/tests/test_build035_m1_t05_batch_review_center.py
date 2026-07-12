from datetime import datetime, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import text
from src.main import app
from src.db.session import SessionLocal
from src.services.tlc_batch_compare_service import ensure_compare_table

client=TestClient(app)

def ready_batch():
    b=client.post("/api/tlc-batches",json={"business_month":"2027-02","title":uuid4().hex,"created_by":"tester"}).json()
    for s in ["IMPORTING","COMPARE","READY_REVIEW"]:
        r=client.post(f"/api/tlc-batches/{b['id']}/transition",json={"new_status":s,"operator":"tester"})
        assert r.status_code==200,r.text
    db=SessionLocal()
    try:
        ensure_compare_table(db)
        db.execute(text("""INSERT INTO tlc_batch_compare_result(
          id,batch_id,excel_file_id,pdf_file_id,request_no,matched,difference_count,
          result_json,status,compared_by,compared_at
        ) VALUES(:id,:b,:e,:p,'REQ-TEST',1,0,:j,'MATCHED','tester',:t)"""),
        {"id":uuid4().hex,"b":b["id"],"e":uuid4().hex,"p":uuid4().hex,
         "j":'{"matched":true,"request_no":"REQ-TEST","difference_count":0,"sources":{"excel":"a.xlsx","pdf":"a.pdf"},"request_document":{"request_no":"REQ-TEST","customer_id":"C001","customer_name":"Test","currency":"JPY","total_amount":"100"}}',
         "t":datetime.now(timezone.utc).isoformat()})
        db.commit()
    finally:db.close()
    return b

def test_review_link_and_status_flow():
    b=ready_batch()
    p=client.get(f"/api/tlc-batches/{b['id']}/review/payload")
    assert p.status_code==200 and p.json()["matched"] is True
    x=client.post(f"/api/tlc-batches/{b['id']}/review/links",json={"pending_review_id":"PR-"+uuid4().hex,"linked_by":"tester"})
    assert x.status_code==200,x.text
    link=x.json()["review_link"]
    assert client.get(f"/api/tlc-batches/{b['id']}").json()["status"]=="REVIEWING"
    u=client.put(f"/api/tlc-batches/{b['id']}/review/links/{link['id']}",json={"review_status":"POSTED","operator":"tester"})
    assert u.status_code==200,u.text
    assert client.get(f"/api/tlc-batches/{b['id']}").json()["status"]=="LEDGER_POSTED"

def test_link_is_idempotent():
    b=ready_batch();pid="PR-"+uuid4().hex
    a=client.post(f"/api/tlc-batches/{b['id']}/review/links",json={"pending_review_id":pid,"linked_by":"tester"})
    z=client.post(f"/api/tlc-batches/{b['id']}/review/links",json={"pending_review_id":pid,"linked_by":"tester"})
    assert a.status_code==200 and z.status_code==200
    assert z.json()["status"]=="exists"

def test_review_tab_connected():
    html=client.get("/batch-center").text
    assert "/review/payload" in html and "/review/links" in html
    assert "/api/requests/pending-review" in html and "送入待审核" in html

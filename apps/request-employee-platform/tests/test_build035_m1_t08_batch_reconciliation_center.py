from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app
client=TestClient(app)
def make_batch():
 b=client.post('/api/tlc-batches',json={'business_month':'2027-05','title':uuid4().hex,'created_by':'tester'}).json()
 for s in ['IMPORTING','COMPARE','READY_REVIEW','REVIEWING','LEDGER_POSTED','BANK_IMPORTED']:
  r=client.post(f"/api/tlc-batches/{b['id']}/transition",json={'new_status':s,'operator':'tester'});assert r.status_code==200,r.text
 return b
def test_flow():
 b=make_batch();r=client.post(f"/api/tlc-batches/{b['id']}/reconciliation/links",json={'reconciliation_id':'REC-'+uuid4().hex,'customer_id':'C001','reconciliation_status':'SETTLED','linked_by':'tester'});assert r.status_code==200,r.text
 assert client.get(f"/api/tlc-batches/{b['id']}").json()['status']=='RECONCILING'
 f=client.post(f"/api/tlc-batches/{b['id']}/reconciliation/finish",json={'operator':'tester'});assert f.status_code==200,f.text;assert f.json()['status']=='FINISHED'
def test_open_blocks_and_idempotent():
 b=make_batch();rid='REC-'+uuid4().hex;p={'reconciliation_id':rid,'customer_id':'C002','reconciliation_status':'UNPAID','linked_by':'tester'}
 a=client.post(f"/api/tlc-batches/{b['id']}/reconciliation/links",json=p);z=client.post(f"/api/tlc-batches/{b['id']}/reconciliation/links",json=p);assert a.status_code==200 and z.json()['status']=='exists'
 assert client.post(f"/api/tlc-batches/{b['id']}/reconciliation/finish",json={'operator':'tester'}).status_code==400
def test_page():
 h=client.get('/batch-center').text
 assert '/reconciliation/links' in h and '/reconciliation/summary' in h and '/reconciliation/finish' in h

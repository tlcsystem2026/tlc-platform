from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app
client=TestClient(app)
def make_batch():
 r=client.post('/api/tlc-batches',json={'business_month':'2027-09','title':uuid4().hex,'created_by':'tester'});assert r.status_code==200,r.text;return r.json()
def test_register_success_error_idempotent_and_page():
 b=make_batch();bid='BANK-'+uuid4().hex
 p={'batch_id':b['id'],'bank_import_id':bid,'source_name':'sugamo.csv','source_reference':'bank-csv:'+bid,'registered_by':'tester','bank_name':'巣鴨信用金庫','record_count':12,'success_count':10,'duplicate_count':2}
 a=client.post('/api/tlc-import-jobs/register-bank-csv',json=p);z=client.post('/api/tlc-import-jobs/register-bank-csv',json=p)
 assert a.status_code==200,a.text;assert a.json()['job']['status']=='SUCCESS';assert z.json()['status']=='exists'
 s=client.get('/api/tlc-import-jobs/bank-csv-summary',params={'batch_id':b['id']});assert s.json()['record_count']==12
 h=client.get('/import-center').text;assert '/api/tlc-import-jobs/register-bank-csv' in h and '登记银行CSV导入结果' in h
def test_error_job():
 b=make_batch();bid='BANK-'+uuid4().hex
 r=client.post('/api/tlc-import-jobs/register-bank-csv',json={'batch_id':b['id'],'bank_import_id':bid,'source_name':'yucho.csv','source_reference':'bank-csv:'+bid,'registered_by':'tester','error_count':1})
 assert r.status_code==200,r.text;assert r.json()['job']['status']=='ERROR'

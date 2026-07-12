from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app
client=TestClient(app)

def make_batch():
    r=client.post('/api/tlc-batches',json={'business_month':'2027-08','title':uuid4().hex,'created_by':'tester'})
    assert r.status_code==200,r.text
    return r.json()

def upload(batch_id,file_type,name,content):
    r=client.post(f'/api/tlc-batches/{batch_id}/request-files',params={'file_type':file_type,'original_name':name,'uploaded_by':'tester'},content=content)
    assert r.status_code==200,r.text

def test_request_files_auto_register_idempotently():
    b=make_batch();upload(b['id'],'REQUEST_EXCEL','request.xlsx',b'PK excel');upload(b['id'],'REQUEST_PDF','request.pdf',b'%PDF')
    a=client.post(f'/api/tlc-import-jobs/sync-request-files/{b["id"]}',json={'operator':'tester'})
    z=client.post(f'/api/tlc-import-jobs/sync-request-files/{b["id"]}',json={'operator':'tester'})
    assert a.status_code==200,a.text
    assert a.json()['created_job_count']==2
    assert z.json()['created_job_count']==0 and z.json()['existing_job_count']==2
    jobs=client.get('/api/tlc-import-jobs',params={'batch_id':b['id']}).json()
    assert len(jobs)==2
    assert {x['import_type'] for x in jobs}=={'REQUEST_EXCEL','REQUEST_PDF'}
    assert {x['status'] for x in jobs}=={'SUCCESS'}

def test_new_version_creates_new_job():
    b=make_batch();upload(b['id'],'REQUEST_EXCEL','request.xlsx',b'PK v1')
    client.post(f'/api/tlc-import-jobs/sync-request-files/{b["id"]}',json={'operator':'tester'})
    upload(b['id'],'REQUEST_EXCEL','request.xlsx',b'PK v2')
    r=client.post(f'/api/tlc-import-jobs/sync-request-files/{b["id"]}',json={'operator':'tester'})
    assert r.status_code==200 and r.json()['created_job_count']==1
    jobs=client.get('/api/tlc-import-jobs',params={'batch_id':b['id'],'import_type':'REQUEST_EXCEL'}).json()
    assert len(jobs)==2

def test_pages_connected():
    assert '/sync-request-files/' in client.get('/batch-center').text
    h=client.get('/import-center').text
    assert '/sync-request-files/' in h and '同步请求书导入任务' in h

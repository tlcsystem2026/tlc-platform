from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app

client=TestClient(app)

def _snapshot():
    r=client.post('/api/tlc-customer-reconciliation-snapshots/calculate',json={
      'customer_id':f'C-{uuid4().hex[:10]}','customer_name':'Recommend Customer',
      'previous_request_cutoff':'2026-01-31','current_request_cutoff':'2026-02-28',
      'previous_bank_cutoff':'2026-01-31','current_bank_cutoff':'2026-02-28','created_by':'tester'})
    assert r.status_code==200,r.text
    return r.json()

def _case():
    s=_snapshot()
    r=client.post('/api/tlc-customer-reconciliation-cases',json={'snapshot_id':s['id'],'operator':'tester'})
    assert r.status_code==200,r.text
    return r.json()['reconciliation']

def test_generate_is_safe_with_empty_evidence():
    c=_case()
    r=client.post('/api/tlc-customer-recommended-matching/generate',json={'reconciliation_id':c['id'],'operator':'tester','minimum_score':70})
    assert r.status_code==200,r.text
    b=r.json();assert b['created_count']==0 and b['recommendation_count']==0

def test_invalid_reconciliation_is_404():
    r=client.post('/api/tlc-customer-recommended-matching/generate',json={'reconciliation_id':uuid4().hex,'operator':'tester'})
    assert r.status_code==404

def test_page_available_and_connected():
    r=client.get('/customer-recommended-matching-center')
    assert r.status_code==200
    h=r.text
    assert 'Customer Recommended Matching Center' in h
    assert '/api/tlc-customer-recommended-matching/generate' in h
    assert 'href="/customer-auto-matching-center"' in h
    assert 'href="/customer-reconciliation-confirmation-center"' in h

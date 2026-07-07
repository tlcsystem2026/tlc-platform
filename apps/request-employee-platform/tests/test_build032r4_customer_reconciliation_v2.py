
from io import BytesIO
from zipfile import ZipFile
from fastapi.testclient import TestClient
from src.main import app
client = TestClient(app)

def test_customer_reconciliation_page_available():
    r=client.get('/api/customer-reconciliation/page')
    assert r.status_code==200
    assert '客户对账清款基准设置' in r.text
    assert '不是按银行账户设置' in r.text
    assert '全数据模糊检索' in r.text

def test_customer_cutoff_confirmed_zero_balance_flow_and_scope():
    payload={'customer_id':'CUST-R4-001','customer_name':'正式测试客户A','request_date_cutoff':'2026-07-31','bank_received_date_cutoff':'2026-08-05','request_total_amount':'125000','bank_receipt_amount':'100000','cash_receipt_amount':'20000','special_writeoff_amount':'5000','manual_adjustment_amount':'0','currency':'JPY','status':'confirmed','note':'现金与核销已确认','confirmed_by':'pytest'}
    r=client.post('/api/customer-reconciliation/cutoffs',json=payload)
    assert r.status_code==200
    body=r.json(); assert body['balance_amount']=='0'
    assert body['next_reconciliation_scope']['next_request_condition']=='request_date > 2026-07-31'
    assert body['next_reconciliation_scope']['next_bank_receipt_condition']=='bank_received_date > 2026-08-05'
    scope=client.get('/api/customer-reconciliation/scope',params={'customer_id':'CUST-R4-001'})
    assert scope.status_code==200
    assert 'bank_received_date <= 2026-08-05' in scope.json()['excluded_bank_receipt_rule']

def test_customer_cutoff_rejects_non_zero_balance_without_special_confirmation():
    payload={'customer_id':'CUST-R4-002','customer_name':'差额测试客户','request_date_cutoff':'2026-07-31','bank_received_date_cutoff':'2026-08-05','request_total_amount':'1000','bank_receipt_amount':'900','status':'confirmed'}
    r=client.post('/api/customer-reconciliation/cutoffs',json=payload)
    assert r.status_code==400
    assert 'balance_amount is not zero' in r.text

def test_customer_cutoff_allows_special_confirmation_with_reason():
    payload={'customer_id':'CUST-R4-003','customer_name':'特别确认客户','request_date_cutoff':'2026-07-31','bank_received_date_cutoff':'2026-08-05','request_total_amount':'1000','bank_receipt_amount':'900','status':'special_confirmed','special_confirm_reason':'汇款手续费差额，经确认特别核销'}
    r=client.post('/api/customer-reconciliation/cutoffs',json=payload)
    assert r.status_code==200
    assert r.json()['balance_amount']=='100'

def test_strict_search_and_keyword_fuzzy_search():
    strict=client.get('/api/customer-reconciliation/cutoffs',params={'customer_id':'CUST-R4-001'})
    assert strict.status_code==200
    assert len(strict.json())==1
    fuzzy=client.get('/api/customer-reconciliation/cutoffs',params={'keyword':'现金与核销'})
    assert fuzzy.status_code==200
    assert any(x['customer_id']=='CUST-R4-001' for x in fuzzy.json())

def test_customer_cutoff_exports_current_result_set():
    xlsx=client.get('/api/customer-reconciliation/cutoffs/export/excel',params={'customer_id':'CUST-R4-001'})
    assert xlsx.status_code==200
    assert 'spreadsheetml.sheet' in xlsx.headers['content-type']
    with ZipFile(BytesIO(xlsx.content)) as z: assert 'xl/workbook.xml' in z.namelist()
    pdf=client.get('/api/customer-reconciliation/cutoffs/export/pdf',params={'customer_id':'CUST-R4-001'})
    assert pdf.status_code==200
    assert pdf.content.startswith(b'%PDF-1.4')

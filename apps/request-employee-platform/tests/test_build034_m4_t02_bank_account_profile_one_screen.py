from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app
client=TestClient(app)
def test_page_and_bank_seed():
 assert client.get('/tlc-bank-account-master').status_code==200
 client.get('/api/tlc-bank-accounts')
 codes={x['code'] for x in client.get('/api/tlc-codes/values',params={'category_code':'BANK'}).json()}
 assert {'SUGAMO_SHINKIN','JAPAN_POST_BANK'}<=codes
def test_create_update_duplicate_guard():
 acct='A-'+uuid4().hex[:8];r=client.post('/api/tlc-bank-accounts',json={'bank_code':'SUGAMO_SHINKIN','account_number':acct,'branch_name':'板橋支店','active':True});assert r.status_code==200
 rec=r.json();rec['branch_name']='更新';assert client.post('/api/tlc-bank-accounts',json=rec).json()['branch_name']=='更新'
 assert client.post('/api/tlc-bank-accounts',json={'bank_code':'SUGAMO_SHINKIN','account_number':acct}).status_code==400
def test_unknown_bank_rejected():assert client.post('/api/tlc-bank-accounts',json={'bank_code':'UNKNOWN','account_number':'1'}).status_code==400

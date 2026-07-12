from fastapi.testclient import TestClient
from src.main import app
client=TestClient(app)
def test_page_and_seed():
 r=client.get('/tlc-code-master');assert r.status_code==200;assert 'TLC Code Master' in r.text
 cats=client.get('/api/tlc-codes/categories');assert cats.status_code==200
 codes={x['category_code'] for x in cats.json()};assert {'BANK','CUSTOMER_STATUS','REVIEW_STATUS','CURRENCY'}<=codes
def test_create_update_and_duplicate():
 p={'category_code':'TEST_MASTER_UI','name_zh':'测试分类','name_ja':'テスト分類','name_en':'Test Category','sort_order':990,'active':True}
 a=client.post('/api/tlc-codes/categories',json=p);assert a.status_code==200
 c=a.json();c['name_en']='Updated';c['active']=False
 b=client.post('/api/tlc-codes/categories',json=c);assert b.status_code==200 and b.json()['active'] is False
 v={'category_code':'TEST_MASTER_UI','code':'VALUE_A','name_zh':'值A','name_ja':'値A','name_en':'Value A','sort_order':10,'active':True,'extra_json':{'source':'pytest'}}
 assert client.post('/api/tlc-codes/values',json=v).status_code==200
 assert client.post('/api/tlc-codes/values',json=v).status_code==400

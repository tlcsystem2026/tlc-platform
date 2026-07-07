from fastapi.testclient import TestClient
from src.main import app
client = TestClient(app)
def test_feature_status_api_lists_ready_and_unfinished_items():
    r=client.get('/api/features'); assert r.status_code==200
    body=r.json(); assert body['build']=='Build032R4'
    features=body['features']
    assert any(x['id']=='sales_search_export' and x['status']=='可验收' for x in features)
    assert any(x['id']=='bank_reconciliation_page' and x['status']=='未完成' for x in features)
def test_acceptance_pages_are_available():
    r=client.get('/acceptance'); assert r.status_code==200
    assert '功能进度核对表' in r.text and '操作指南' in r.text and '未完成 / 入口展示' in r.text
    guide=client.get('/acceptance/guide/sales_search_export'); assert guide.status_code==200
    assert '销售一览检索与导出' in guide.text and '验收标准' in guide.text
def test_dashboard_contains_feature_progress_section():
    r=client.get('/dashboard'); assert r.status_code==200
    assert 'feature-progress' in r.text and '/api/features' in r.text

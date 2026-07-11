from fastapi.testclient import TestClient
from src.main import app

client=TestClient(app)

def test_bank_import_page_available_and_bound():
    r=client.get("/bank-import")
    assert r.status_code==200
    html=r.text
    assert "银行流水导入与查看" in html
    assert "/api/bank-import/csv" in html
    assert "/api/bank-import/transactions" in html
    assert "/api/bank-import/summary" in html
    assert "SUGAMO_SHINKIN" in html
    assert "JAPAN_POST_BANK" in html

def test_bank_transaction_list_and_summary_endpoints():
    rows=client.get("/api/bank-import/transactions",params={"limit":10})
    assert rows.status_code==200
    assert isinstance(rows.json(),list)
    summary=client.get("/api/bank-import/summary")
    assert summary.status_code==200
    body=summary.json()
    assert {"transaction_count","credit_count","credit_total","debit_count","debit_total"} <= set(body)

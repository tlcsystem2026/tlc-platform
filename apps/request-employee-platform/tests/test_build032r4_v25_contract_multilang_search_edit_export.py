
from io import BytesIO
from zipfile import ZipFile
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)
PAYLOAD = {"customer_id":"V25-C1","customer_name":"Multilang Alpha","request_date_cutoff":"2026-07-31","bank_received_date_cutoff":"2026-08-05","request_total_amount":"1000","bank_receipt_amount":"900","cash_receipt_amount":"100","special_writeoff_amount":"0","manual_adjustment_amount":"0","currency":"JPY","status":"confirmed","confirmed_by":"tester","note":"FuzzyKey ABC"}

def test_v25_preserves_old_contracts_and_page_tokens():
    page=client.get("/api/customer-reconciliation/page")
    assert page.status_code==200
    for token in ["客户对账清款基准设置","不是按银行账户设置","中文","日本語","English","<thead>","headers","editRow","全数据模糊检索"]:
        assert token in page.text
    result=client.post("/api/customer-reconciliation/cutoffs",json=PAYLOAD)
    assert result.status_code==200
    body=result.json()
    assert body["balance_amount"]=="0"
    assert body["next_reconciliation_scope"]["next_request_condition"]=="request_date > 2026-07-31"
    assert body["next_reconciliation_scope"]["next_bank_receipt_condition"]=="bank_received_date > 2026-08-05"
    assert "cash_collection" in body["payment_sources"]
    bad={**PAYLOAD,"customer_id":"V25-BAD","request_total_amount":"1000","bank_receipt_amount":"900","cash_receipt_amount":"0"}
    bad_result=client.post("/api/customer-reconciliation/cutoffs",json=bad)
    assert bad_result.status_code==400
    assert "balance_amount is not zero" in bad_result.text

def test_v25_search_edit_history_and_safe_exports():
    assert len(client.get("/api/customer-reconciliation/cutoffs",params={"customer_id":"V25-C1"}).json())==1
    assert any(row["customer_id"]=="V25-C1" for row in client.get("/api/customer-reconciliation/cutoffs",params={"keyword":"ABC"}).json())
    assert client.get("/api/customer-reconciliation/cutoffs/V25-C1").json()["customer_name"]=="Multilang Alpha"
    changed={**PAYLOAD,"note":"updated","change_reason":"targeted edit"}
    assert client.post("/api/customer-reconciliation/cutoffs",json=changed).status_code==200
    history=client.get("/api/customer-reconciliation/history",params={"customer_id":"V25-C1"}).json()
    assert len(history)>=2
    assert history[-1]["event"]=="update"
    assert history[-1]["old"] is not None
    xlsx=client.get("/api/customer-reconciliation/cutoffs/export/excel",params={"customer_id":"V25-C1","lang":"en"})
    assert xlsx.status_code==200
    assert "spreadsheetml.sheet" in xlsx.headers["content-type"]
    with ZipFile(BytesIO(xlsx.content)) as archive:
        xml=b"".join(archive.read(name) for name in archive.namelist() if name.endswith(".xml"))
        assert b"Customer" in xml
        assert b"V25-C1" in xml
    pdf=client.get("/api/customer-reconciliation/cutoffs/export/pdf",params={"customer_id":"V25-C1","lang":"en"})
    assert pdf.status_code==200
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content)>500


from io import BytesIO
from zipfile import ZipFile
from fastapi.testclient import TestClient
from src.main import app

client=TestClient(app)
ROW={"customer_id":"LIKE-ABC-2601","customer_name":"Tokyo Example Trading","request_date_cutoff":"2026-07-31","bank_received_date_cutoff":"2026-08-05","request_total_amount":"1000","bank_receipt_amount":"900","cash_receipt_amount":"100","special_writeoff_amount":"0","manual_adjustment_amount":"0","currency":"JPY","status":"confirmed","confirmed_by":"v26","note":"visible-row"}

def setup_module():
    assert client.post("/api/customer-reconciliation/cutoffs",json=ROW).status_code==200

def test_high_priority_business_explanation_and_like_search():
    page=client.get("/api/customer-reconciliation/page").text
    for token in ["业务说明","業務説明","Business Explanation","按客户设置","銀行口座単位","partial match","部分匹配","部分一致"]:
        assert token in page
    by_id=client.get("/api/customer-reconciliation/cutoffs",params={"customer_id":"abc-26"}).json()
    assert any(x["customer_id"]=="LIKE-ABC-2601" for x in by_id)
    by_name=client.get("/api/customer-reconciliation/cutoffs",params={"customer_name":"example trad"}).json()
    assert any(x["customer_id"]=="LIKE-ABC-2601" for x in by_name)

def test_high_priority_wysiwyg_excel_result_only():
    r=client.get("/api/customer-reconciliation/cutoffs/export/excel",params={"customer_id":"abc-26","lang":"en"})
    assert r.status_code==200
    with ZipFile(BytesIO(r.content)) as z:
        xml=b"".join(z.read(n) for n in z.namelist() if n.endswith(".xml"))
    assert b"LIKE-ABC-2601" in xml
    assert b"Customer ID" in xml
    assert b"Action" not in xml and b"Edit" not in xml
    assert b"Filters" not in xml and b"Exported At" not in xml
    assert b"Total" in xml

def test_high_priority_wysiwyg_pdf_and_empty_result():
    r=client.get("/api/customer-reconciliation/cutoffs/export/pdf",params={"customer_id":"abc-26","lang":"en"})
    assert r.status_code==200 and r.content.startswith(b"%PDF") and len(r.content)>500
    empty=client.get("/api/customer-reconciliation/cutoffs/export/excel",params={"customer_id":"NO-SUCH-V26","lang":"en"})
    assert empty.status_code==200
    with ZipFile(BytesIO(empty.content)) as z:
        xml=b"".join(z.read(n) for n in z.namelist() if n.endswith(".xml"))
    assert b"Customer ID" in xml
    assert b"Total" in xml

def test_medium_low_priority_multilang_search_labels_and_buttons():
    page=client.get("/api/customer-reconciliation/page").text
    for token in ["全数据模糊检索","全データあいまい検索","All-data fuzzy search","Excel导出","Excel出力","Export Excel","保存/更新","新規","Reset"]:
        assert token in page

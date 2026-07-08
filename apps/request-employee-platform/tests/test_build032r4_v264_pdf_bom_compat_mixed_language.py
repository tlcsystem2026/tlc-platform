from fastapi.testclient import TestClient
from src.main import app
client=TestClient(app)
ROW={"customer_id":"PDF-V264-中文-A","customer_name":"東京顧客 Alpha","request_date_cutoff":"2026-07-31","bank_received_date_cutoff":"2026-08-05","request_total_amount":"3210","bank_receipt_amount":"3000","cash_receipt_amount":"210","special_writeoff_amount":"0","manual_adjustment_amount":"0","currency":"JPY","status":"confirmed","confirmed_by":"unicode-test","note":"中文 日本語 English"}
def setup_module(): assert client.post("/api/customer-reconciliation/cutoffs",json=ROW).status_code==200
def bomhex(text): return ("feff"+text.encode("utf-16-be").hex()).encode("ascii")
def test_pdf_bom_compatibility_and_mixed_language():
    for lang,header in [("zh","客户ID"),("ja","顧客ID"),("en","Customer ID")]:
        r=client.get("/api/customer-reconciliation/cutoffs/export/pdf",params={"customer_id":"V264","lang":lang})
        assert r.status_code==200 and r.content.startswith(b"%PDF")
        assert bomhex(header) in r.content
        assert bomhex("PDF-V264-中文-A") in r.content
        assert b"/Identity-H" not in r.content
        assert b"/UniGB-UCS2-H" in r.content and b"/UniJIS-UCS2-H" in r.content
def test_pdf_and_list_share_partial_filtering():
    rows=client.get("/api/customer-reconciliation/cutoffs",params={"customer_name":"Alpha"}).json()
    assert any(x["customer_id"]=="PDF-V264-中文-A" for x in rows)
    r=client.get("/api/customer-reconciliation/cutoffs/export/pdf",params={"customer_name":"Alpha","lang":"en"})
    assert r.status_code==200 and bomhex("PDF-V264-中文-A") in r.content

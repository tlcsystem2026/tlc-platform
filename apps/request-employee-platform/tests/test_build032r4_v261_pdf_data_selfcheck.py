
from fastapi.testclient import TestClient
from src.main import app

client=TestClient(app)

A={"customer_id":"PDF-DATA-261-A","customer_name":"PDF Alpha","request_date_cutoff":"2026-07-31","bank_received_date_cutoff":"2026-08-05","request_total_amount":"1200","bank_receipt_amount":"1000","cash_receipt_amount":"200","special_writeoff_amount":"0","manual_adjustment_amount":"0","currency":"JPY","status":"confirmed","confirmed_by":"pdf-test","note":"must appear"}
B={**A,"customer_id":"PDF-DATA-261-B","customer_name":"PDF Beta","note":"must not appear in A filter"}

def setup_module():
    assert client.post("/api/customer-reconciliation/cutoffs",json=A).status_code==200
    assert client.post("/api/customer-reconciliation/cutoffs",json=B).status_code==200

def u16hex(text):
    return ("feff"+text.encode("utf-16-be").hex()).encode("ascii")

def test_pdf_contains_real_filtered_result_data_and_header():
    r=client.get("/api/customer-reconciliation/cutoffs/export/pdf",params={"customer_id":"261-A","lang":"en"})
    assert r.status_code==200
    assert r.content.startswith(b"%PDF")
    assert len(r.content)>700
    assert u16hex("PDF-DATA-261-A") in r.content
    assert u16hex("Customer ID") in r.content
    assert u16hex("PDF-DATA-261-B") not in r.content

def test_pdf_uses_same_like_filtering_as_list_and_excel():
    rows=client.get("/api/customer-reconciliation/cutoffs",params={"customer_name":"alpha"}).json()
    assert any(x["customer_id"]=="PDF-DATA-261-A" for x in rows)
    r=client.get("/api/customer-reconciliation/cutoffs/export/pdf",params={"customer_name":"alpha","lang":"en"})
    assert r.status_code==200
    assert u16hex("PDF-DATA-261-A") in r.content

def test_pdf_empty_result_still_has_header_and_total():
    r=client.get("/api/customer-reconciliation/cutoffs/export/pdf",params={"customer_id":"NO-SUCH-261","lang":"en"})
    assert r.status_code==200
    assert u16hex("Customer ID") in r.content
    assert u16hex("Total") in r.content

def test_pdf_endpoint_has_runtime_selfcheck_contract():
    import inspect
    from src.api.routes import customer_reconciliation as mod
    source=inspect.getsource(mod._selfcheck_pdf)
    assert "result data missing" in source
    assert "header missing" in source

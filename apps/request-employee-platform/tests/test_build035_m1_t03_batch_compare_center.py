from types import SimpleNamespace
from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app
import src.services.tlc_batch_compare_service as svc

client=TestClient(app)

def make_batch():
    r=client.post("/api/tlc-batches",json={"business_month":"2026-12","title":uuid4().hex,"created_by":"tester"})
    assert r.status_code==200,r.text
    b=r.json()
    for ft,name,content in [
        ("REQUEST_EXCEL","a.xlsx",b"PK excel"),
        ("REQUEST_PDF","a.pdf",b"%PDF-1.4"),
    ]:
        u=client.post(f"/api/tlc-batches/{b['id']}/request-files",params={"file_type":ft,"original_name":name,"uploaded_by":"tester"},content=content)
        assert u.status_code==200,u.text
    return b

def mock_compare(monkeypatch,matched):
    monkeypatch.setattr(svc,"_parse_excel",lambda c,n:SimpleNamespace())
    monkeypatch.setattr(svc,"_parse_pdf",lambda c,n:SimpleNamespace())
    monkeypatch.setattr(svc,"compare_request_documents",lambda e,p:SimpleNamespace(matched=matched,request_no="REQ-1",differences=[]))
    monkeypatch.setattr(svc,"to_legacy_compare_payload",lambda r:{
        "matched":matched,"request_no":"REQ-1",
        "difference_count":0 if matched else 1,
        "differences":[] if matched else [{"field":"total_amount","excel_value":"100","pdf_value":"90","message":"mismatch"}],
    })

def test_matched_moves_to_ready_review(monkeypatch):
    b=make_batch();mock_compare(monkeypatch,True)
    r=client.post(f"/api/tlc-batches/{b['id']}/compare",json={"compared_by":"tester"})
    assert r.status_code==200,r.text
    assert r.json()["compare_result"]["matched"] is True
    assert client.get(f"/api/tlc-batches/{b['id']}").json()["status"]=="READY_REVIEW"

def test_error_moves_to_error(monkeypatch):
    b=make_batch();mock_compare(monkeypatch,False)
    r=client.post(f"/api/tlc-batches/{b['id']}/compare",json={"compared_by":"tester"})
    assert r.status_code==200,r.text
    assert r.json()["compare_result"]["difference_count"]==1
    assert client.get(f"/api/tlc-batches/{b['id']}").json()["status"]=="ERROR"

def test_same_pair_is_idempotent(monkeypatch):
    b=make_batch();mock_compare(monkeypatch,True)
    a=client.post(f"/api/tlc-batches/{b['id']}/compare",json={"compared_by":"tester"})
    z=client.post(f"/api/tlc-batches/{b['id']}/compare",json={"compared_by":"tester"})
    assert a.status_code==200 and z.status_code==200
    assert z.json()["status"]=="exists"
    assert a.json()["compare_result"]["id"]==z.json()["compare_result"]["id"]

def test_compare_tab_connected():
    html=client.get("/batch-center").text
    assert "/compare/latest" in html and "/compare/history" in html
    assert "执行 Excel / PDF 比较" in html


def test_adapter_parser_name_resolution_supports_existing_contract(monkeypatch):
    marker = object()

    monkeypatch.setattr(
        svc.excel_adapter,
        "parse_request_excel_document",
        lambda content, source_name=None: marker,
        raising=False,
    )

    assert svc._parse_excel(b"excel", "request.xlsx") is marker

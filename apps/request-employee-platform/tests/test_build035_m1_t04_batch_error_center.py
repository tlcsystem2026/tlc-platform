from types import SimpleNamespace
from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app
import src.services.tlc_batch_compare_service as compare_service

client=TestClient(app)

def prepare(monkeypatch):
    b=client.post("/api/tlc-batches",json={"business_month":"2027-01","title":uuid4().hex,"created_by":"tester"}).json()
    for ft,name,data in [("REQUEST_EXCEL","a.xlsx",b"PK"),("REQUEST_PDF","a.pdf",b"%PDF")]:
        assert client.post(f"/api/tlc-batches/{b['id']}/request-files",params={"file_type":ft,"original_name":name,"uploaded_by":"tester"},content=data).status_code==200
    monkeypatch.setattr(compare_service,"_parse_excel",lambda c,n:SimpleNamespace())
    monkeypatch.setattr(compare_service,"_parse_pdf",lambda c,n:SimpleNamespace())
    monkeypatch.setattr(compare_service,"compare_request_documents",lambda e,p:SimpleNamespace(matched=False,request_no="R",differences=[]))
    monkeypatch.setattr(compare_service,"to_legacy_compare_payload",lambda r:{"matched":False,"request_no":"R","difference_count":2,"differences":[{"field":"customer_id","excel_value":"C1","pdf_value":"C9","message":"mismatch"},{"field":"total_amount","excel_value":"100","pdf_value":"90","message":"mismatch"}]})
    assert client.post(f"/api/tlc-batches/{b['id']}/compare",json={"compared_by":"tester"}).status_code==200
    return b

def test_error_sync_update_export_and_reopen(monkeypatch):
    b=prepare(monkeypatch)
    s=client.post(f"/api/tlc-batches/{b['id']}/errors/sync",json={"operator":"tester"})
    assert s.status_code==200 and s.json()["inserted"]==2
    rows=client.get(f"/api/tlc-batches/{b['id']}/errors").json();assert len(rows)==2
    u=client.put(f"/api/tlc-batches/{b['id']}/errors/{rows[0]['id']}",json={"status":"RESOLVED","operator":"tester","resolution_note":"fixed"})
    assert u.status_code==200 and u.json()["status"]=="RESOLVED"
    sm=client.get(f"/api/tlc-batches/{b['id']}/errors/summary").json();assert sm["resolved"]==1 and sm["open"]==1
    ex=client.get(f"/api/tlc-batches/{b['id']}/errors/export.csv");assert ex.status_code==200 and ex.content.startswith(b"\xef\xbb\xbf")
    ro=client.post(f"/api/tlc-batches/{b['id']}/errors/reopen-import",json={"operator":"tester"});assert ro.status_code==200 and ro.json()["status"]=="IMPORTING"

def test_error_tab_connected():
    h=client.get("/batch-center").text
    assert "/errors/sync" in h and "/errors/export.csv" in h and "Error Center" in h

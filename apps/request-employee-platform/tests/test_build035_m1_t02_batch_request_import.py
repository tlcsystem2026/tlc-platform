from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def create_batch():
    r=client.post("/api/tlc-batches",json={"business_month":"2026-11","title":uuid4().hex,"created_by":"tester"})
    assert r.status_code==200,r.text
    return r.json()

def test_upload_version_duplicate_and_readiness():
    b=create_batch()
    x1=client.post(f"/api/tlc-batches/{b['id']}/request-files",params={"file_type":"REQUEST_EXCEL","original_name":"a.xlsx","uploaded_by":"tester"},content=b"PK excel 1")
    assert x1.status_code==200,x1.text
    x2=client.post(f"/api/tlc-batches/{b['id']}/request-files",params={"file_type":"REQUEST_EXCEL","original_name":"a.xlsx","uploaded_by":"tester"},content=b"PK excel 2")
    assert x2.status_code==200 and x2.json()["file"]["version_no"]==2
    dup=client.post(f"/api/tlc-batches/{b['id']}/request-files",params={"file_type":"REQUEST_EXCEL","original_name":"copy.xlsx","uploaded_by":"tester"},content=b"PK excel 2")
    assert dup.status_code==200 and dup.json()["status"]=="duplicate"
    before=client.get(f"/api/tlc-batches/{b['id']}/request-import-readiness").json()
    assert before["missing_file_types"]==["REQUEST_PDF"]
    pdf=client.post(f"/api/tlc-batches/{b['id']}/request-files",params={"file_type":"REQUEST_PDF","original_name":"a.pdf","uploaded_by":"tester"},content=b"%PDF-1.4")
    assert pdf.status_code==200,pdf.text
    ready=client.get(f"/api/tlc-batches/{b['id']}/request-import-readiness").json()
    assert ready["ready_for_compare"] is True
    files=client.get(f"/api/tlc-batches/{b['id']}/request-files").json()
    assert sum(1 for x in files if x["file_type"]=="REQUEST_EXCEL" and x["active"])==1
    logs=client.get(f"/api/tlc-batches/{b['id']}/import-logs").json()
    assert {"SUCCESS","DUPLICATE"} <= {x["status"] for x in logs}

def test_first_upload_moves_batch_to_importing():
    b=create_batch()
    r=client.post(f"/api/tlc-batches/{b['id']}/request-files",params={"file_type":"REQUEST_PDF","original_name":"a.pdf","uploaded_by":"tester"},content=b"%PDF")
    assert r.status_code==200
    assert client.get(f"/api/tlc-batches/{b['id']}").json()["status"]=="IMPORTING"

def test_batch_center_has_connected_request_import_tab():
    html=client.get("/batch-center").text
    assert "/request-files" in html
    assert "/request-import-readiness" in html
    assert "/import-logs" in html
    assert "上传Excel" in html and "上传PDF" in html

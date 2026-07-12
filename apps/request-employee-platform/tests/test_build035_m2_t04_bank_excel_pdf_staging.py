
from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def batch():
    response = client.post("/api/tlc-batches", json={
        "business_month": "2027-10",
        "title": f"Bank Stage {uuid4().hex[:8]}",
        "created_by": "tester",
    })
    assert response.status_code == 200, response.text
    return response.json()

def stage(batch_id, document_type, name, content):
    response = client.post(
        "/api/tlc-import-jobs/stage-bank-document",
        params={
            "batch_id": batch_id,
            "document_type": document_type,
            "original_name": name,
            "source_reference": f"SRC-{uuid4().hex}",
            "staged_by": "tester",
        },
        content=content,
    )
    assert response.status_code == 200, response.text
    return response.json()

def test_excel_stage_to_ready():
    b = batch()
    result = stage(b["id"], "BANK_EXCEL", "statement.xlsx", b"PK excel")
    assert result["stage"]["stage_status"] == "STAGED"
    validated = client.put(
        f"/api/tlc-import-jobs/bank-document-stages/{result['stage']['id']}",
        json={"stage_status": "VALIDATED", "operator": "tester", "parser_contract": "BANK_EXCEL_V1"},
    )
    assert validated.status_code == 200
    ready = client.put(
        f"/api/tlc-import-jobs/bank-document-stages/{result['stage']['id']}",
        json={"stage_status": "READY", "operator": "tester"},
    )
    assert ready.status_code == 200
    jobs = client.get("/api/tlc-import-jobs", params={"batch_id": b["id"], "import_type": "BANK_EXCEL"})
    assert jobs.json()[0]["status"] == "SUCCESS"

def test_pdf_dedup_and_extension_validation():
    b = batch()
    content = b"%PDF-1.4"
    first = stage(b["id"], "BANK_PDF", "statement.pdf", content)
    second = client.post(
        "/api/tlc-import-jobs/stage-bank-document",
        params={
            "batch_id": b["id"], "document_type": "BANK_PDF",
            "original_name": "copy.pdf", "source_reference": f"SRC-{uuid4().hex}",
            "staged_by": "tester",
        },
        content=content,
    )
    assert second.status_code == 200
    assert second.json()["status"] == "exists"
    assert second.json()["stage"]["id"] == first["stage"]["id"]

    invalid = client.post(
        "/api/tlc-import-jobs/stage-bank-document",
        params={
            "batch_id": b["id"], "document_type": "BANK_PDF",
            "original_name": "wrong.xlsx", "source_reference": f"SRC-{uuid4().hex}",
            "staged_by": "tester",
        },
        content=b"PK",
    )
    assert invalid.status_code == 400

def test_summary_and_page():
    b = batch()
    stage(b["id"], "BANK_EXCEL", "a.xlsx", b"PK A")
    stage(b["id"], "BANK_PDF", "b.pdf", b"%PDF B")
    summary = client.get("/api/tlc-import-jobs/bank-document-stage-summary", params={"batch_id": b["id"]})
    assert summary.status_code == 200
    assert summary.json()["stage_count"] == 2
    html = client.get("/import-center").text
    assert "/api/tlc-import-jobs/stage-bank-document" in html
    assert "暂存银行Excel/PDF" in html

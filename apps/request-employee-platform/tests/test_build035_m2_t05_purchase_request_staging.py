
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def _batch():
    response = client.post("/api/tlc-batches", json={
        "business_month": "2027-11",
        "title": f"Purchase Stage {uuid4().hex[:8]}",
        "created_by": "tester",
    })
    assert response.status_code == 200, response.text
    return response.json()


def _stage(batch_id: str, document_type: str, name: str, content: bytes):
    response = client.post(
        "/api/tlc-import-jobs/stage-purchase-document",
        params={
            "batch_id": batch_id,
            "document_type": document_type,
            "original_name": name,
            "source_reference": f"SRC-{uuid4().hex}",
            "staged_by": "tester",
            "supplier_name": "Test Supplier",
            "request_reference": "PR-001",
            "currency": "JPY",
            "total_amount": "1200",
        },
        content=content,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_purchase_excel_stage_to_ready():
    batch = _batch()
    result = _stage(
        batch["id"],
        "PURCHASE_EXCEL",
        "purchase.xlsx",
        b"PK purchase excel",
    )
    assert result["stage"]["stage_status"] == "STAGED"

    validated = client.put(
        f"/api/tlc-import-jobs/purchase-document-stages/{result['stage']['id']}",
        json={
            "stage_status": "VALIDATED",
            "operator": "tester",
            "parser_contract": "PURCHASE_EXCEL_V1",
        },
    )
    assert validated.status_code == 200

    ready = client.put(
        f"/api/tlc-import-jobs/purchase-document-stages/{result['stage']['id']}",
        json={
            "stage_status": "READY",
            "operator": "tester",
        },
    )
    assert ready.status_code == 200

    jobs = client.get(
        "/api/tlc-import-jobs",
        params={
            "batch_id": batch["id"],
            "import_type": "PURCHASE_EXCEL",
        },
    )
    assert jobs.status_code == 200
    assert jobs.json()[0]["status"] == "SUCCESS"


def test_purchase_pdf_and_image_are_supported_and_deduplicated():
    batch = _batch()

    pdf = _stage(
        batch["id"],
        "PURCHASE_PDF",
        "invoice.pdf",
        b"%PDF-1.4 invoice",
    )
    image = _stage(
        batch["id"],
        "PURCHASE_IMAGE",
        "receipt.jpg",
        b"fake-jpeg-content",
    )

    assert pdf["stage"]["document_type"] == "PURCHASE_PDF"
    assert image["stage"]["document_type"] == "PURCHASE_IMAGE"

    duplicate = client.post(
        "/api/tlc-import-jobs/stage-purchase-document",
        params={
            "batch_id": batch["id"],
            "document_type": "PURCHASE_IMAGE",
            "original_name": "copy.jpg",
            "source_reference": f"SRC-{uuid4().hex}",
            "staged_by": "tester",
        },
        content=b"fake-jpeg-content",
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "exists"
    assert duplicate.json()["stage"]["id"] == image["stage"]["id"]


def test_invalid_extension_is_rejected():
    batch = _batch()
    response = client.post(
        "/api/tlc-import-jobs/stage-purchase-document",
        params={
            "batch_id": batch["id"],
            "document_type": "PURCHASE_PDF",
            "original_name": "wrong.xlsx",
            "source_reference": f"SRC-{uuid4().hex}",
            "staged_by": "tester",
        },
        content=b"PK",
    )
    assert response.status_code == 400
    assert "PURCHASE_PDF requires .pdf" in response.json()["detail"]


def test_summary_and_import_center_connection():
    batch = _batch()
    _stage(batch["id"], "PURCHASE_EXCEL", "a.xlsx", b"PK A")
    _stage(batch["id"], "PURCHASE_PDF", "b.pdf", b"%PDF B")
    _stage(batch["id"], "PURCHASE_IMAGE", "c.png", b"PNG C")

    summary = client.get(
        "/api/tlc-import-jobs/purchase-document-stage-summary",
        params={"batch_id": batch["id"]},
    )
    assert summary.status_code == 200
    assert summary.json()["stage_count"] == 3
    assert summary.json()["excel_count"] == 1
    assert summary.json()["pdf_count"] == 1
    assert summary.json()["image_count"] == 1

    html = client.get("/import-center").text
    assert "/api/tlc-import-jobs/stage-purchase-document" in html
    assert "暂存采购Excel/PDF/图片" in html

from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_bank_reconciliation_cutoff_is_persistent_and_calculates_next_start():
    payload = {
        "legal_entity_id": "TEST-JP-01",
        "bank_account_id": "JPBANK-001",
        "bank_name": "Japan Post Bank",
        "last_reconciled_date": "2026-07-20",
        "updated_by": "pytest",
    }
    r = client.post("/api/bank/reconciliation/settings", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["last_reconciled_date"] == "2026-07-20"
    assert body["current_start_date"] == "2026-07-21"

    r2 = client.get("/api/bank/reconciliation/settings", params={
        "legal_entity_id": "TEST-JP-01",
        "bank_account_id": "JPBANK-001",
    })
    assert r2.status_code == 200
    rows = r2.json()
    assert len(rows) >= 1
    assert rows[0]["current_start_date"] == "2026-07-21"


def test_bank_reconciliation_period_endpoint():
    r = client.get("/api/bank/reconciliation/period", params={
        "legal_entity_id": "TEST-JP-01",
        "bank_account_id": "JPBANK-001",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["last_reconciled_date"]
    assert body["current_start_date"]


def test_bank_reconciliation_settings_exports():
    xlsx = client.get("/api/bank/reconciliation/settings/export/excel")
    assert xlsx.status_code == 200
    assert "spreadsheetml.sheet" in xlsx.headers["content-type"]
    with ZipFile(BytesIO(xlsx.content)) as z:
        assert "xl/workbook.xml" in z.namelist()

    pdf = client.get("/api/bank/reconciliation/settings/export/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF-1.4")


from uuid import uuid4
from fastapi.testclient import TestClient
from src.main import app

client=TestClient(app)

def _snapshot():
    r=client.post("/api/tlc-customer-reconciliation-snapshots/calculate",json={
      "customer_id":f"C-{uuid4().hex[:10]}","customer_name":"Auto Match Customer",
      "previous_request_cutoff":"2026-01-31","current_request_cutoff":"2026-02-28",
      "previous_bank_cutoff":"2026-01-31","current_bank_cutoff":"2026-02-28","created_by":"tester"})
    assert r.status_code==200,r.text
    return r.json()

def _case():
    s=_snapshot()
    r=client.post("/api/tlc-customer-reconciliation-cases",json={"snapshot_id":s["id"],"operator":"tester"})
    assert r.status_code==200,r.text
    return r.json()["reconciliation"]

def test_generate_is_safe_with_empty_evidence():
    c=_case()
    r=client.post("/api/tlc-customer-auto-matching/generate",json={"reconciliation_id":c["id"],"operator":"tester"})
    assert r.status_code==200,r.text
    body=r.json()
    assert body["created_count"]==0
    assert body["proposal_count"]==0

def test_invalid_reconciliation_is_404():
    r=client.post("/api/tlc-customer-auto-matching/generate",json={"reconciliation_id":uuid4().hex,"operator":"tester"})
    assert r.status_code==404

def test_page_available_and_connected():
    r=client.get("/customer-auto-matching-center")
    assert r.status_code==200
    h=r.text
    assert "Customer Auto Matching Center" in h
    assert "/api/tlc-customer-auto-matching/generate" in h
    assert 'href="/customer-reconciliation-confirmation-center"' in h
    assert 'href="/sales-ledger-evidence-center"' in h
    assert 'href="/bank-payment-evidence-center"' in h


def test_legacy_audit_schema_is_upgraded():
    from sqlalchemy import text
    from src.db.session import SessionLocal
    from src.services.tlc_customer_reconciliation_case_service import ensure_tables

    db = SessionLocal()
    try:
        db.execute(text("DROP TABLE IF EXISTS tlc_customer_reconciliation_audit"))
        db.execute(text("""
            CREATE TABLE tlc_customer_reconciliation_audit (
                id VARCHAR(64) PRIMARY KEY,
                event_type VARCHAR(128) NOT NULL DEFAULT ''
            )
        """))
        db.commit()
        ensure_tables(db)
        columns = {
            row[1]
            for row in db.execute(
                text("PRAGMA table_info(tlc_customer_reconciliation_audit)")
            ).all()
        }
        assert "reconciliation_id" in columns
        assert "snapshot_id" in columns
        assert "message" in columns
    finally:
        db.close()

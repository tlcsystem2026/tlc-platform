import os
import tempfile
from pathlib import Path
from uuid import uuid4


TEST_DB = Path(tempfile.gettempdir()) / f"tlc_guided_current_{uuid4().hex}.sqlite3"
os.environ["TLC_DATABASE_URL"] = "sqlite:///" + TEST_DB.as_posix()

from fastapi.testclient import TestClient
from sqlalchemy import text

from src.db.session import SessionLocal
from src.main import app
from src.services.tlc_guided_monthly_workflow_service import guided_monthly_workflow


client = TestClient(app)


def _prepare_complete_month(db):
    statements = [
        "CREATE TABLE tlc_customer_master(customer_id TEXT)",
        "CREATE TABLE tlc_bank_account_profile(id TEXT)",
        "CREATE TABLE tlc_request_batch_compare(id TEXT,business_month TEXT,status TEXT,exception_count INTEGER,error_count INTEGER,is_current INTEGER)",
        "CREATE TABLE tlc_request_review_queue(id TEXT,business_month TEXT,is_current INTEGER)",
        "CREATE TABLE request_pending_review(id TEXT,business_month TEXT,status TEXT)",
        "CREATE TABLE formal_sales_request_ledger(id TEXT,pending_review_id TEXT,request_date TEXT,status TEXT)",
        "CREATE TABLE bank_transaction_import(id TEXT,transaction_date TEXT)",
        "CREATE TABLE tlc_customer_recommended_match(id TEXT,status TEXT)",
        "CREATE TABLE tlc_customer_reconciliation_snapshot(id TEXT,created_at TEXT)",
        "CREATE TABLE tlc_customer_reconciliation_confirmation(id TEXT,status TEXT,confirmed_at TEXT)",
        "CREATE TABLE tlc_monthly_close_signoff(id TEXT,business_month TEXT,status TEXT)",
        "INSERT INTO tlc_customer_master VALUES('C1')",
        "INSERT INTO tlc_bank_account_profile VALUES('B1')",
        "INSERT INTO tlc_request_batch_compare VALUES('BATCH1','202608','COMPLETED',0,0,1)",
        "INSERT INTO tlc_request_review_queue VALUES('R1','202608',1)",
        "INSERT INTO request_pending_review VALUES('P1','202608','APPROVED')",
        "INSERT INTO formal_sales_request_ledger VALUES('L1','P1','2026-08-10','ACTIVE')",
        "INSERT INTO bank_transaction_import VALUES('T1','2026-08-12')",
        "INSERT INTO tlc_customer_recommended_match VALUES('M1','ACCEPTED')",
        "INSERT INTO tlc_customer_reconciliation_snapshot VALUES('S1','2026-08-20T10:00:00')",
        "INSERT INTO tlc_customer_reconciliation_confirmation VALUES('C1','CONFIRMED','2026-08-21T10:00:00')",
        "INSERT INTO tlc_monthly_close_signoff VALUES('MC1','202608','APPROVED')",
    ]
    for sql in statements:
        db.execute(text(sql))
    db.commit()


def test_current_workflow_uses_real_business_pages_and_completion_sources():
    db = SessionLocal()
    try:
        empty = guided_monthly_workflow(db, business_month="2026-08")
        assert empty["next_step_code"] == "MASTER_SETUP"
        _prepare_complete_month(db)
        result = guided_monthly_workflow(db, business_month="2026-08")
        assert result["all_complete"] is True
        assert result["completed_step_count"] == 8
        paths = [item["path"] for item in result["steps"]]
        assert paths == [
            "/system-parameter-center",
            "/request-review-center",
            "/requests/review-workbench",
            "/sales",
            "/bank-import",
            "/customer-recommended-matching-center",
            "/customer-payment-reconciliation",
            "/monthly-close-center",
        ]
    finally:
        db.close()


def test_guided_page_explains_current_business_sequence():
    response = client.get("/guided-monthly-workflow")
    assert response.status_code == 200
    html = response.text
    assert "月度业务引导" in html
    assert "请求书导入 Batch 与文件核对" not in html
    assert "/api/tlc-guided-monthly-workflow" in html
    assert "业务审核" in html
    assert "正式销售" in html
    assert "客户匹配" in html

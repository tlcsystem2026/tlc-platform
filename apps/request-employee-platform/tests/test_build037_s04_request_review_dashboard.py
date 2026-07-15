from fastapi.testclient import TestClient
from sqlalchemy import text
from src.main import app
from src.db.session import SessionLocal
from src.services.request_review_service import ensure_review_tables

client = TestClient(app)

def seed():
    db = SessionLocal()
    try:
        db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_request_batch_compare_item(
            id VARCHAR(64) PRIMARY KEY,batch_id VARCHAR(64),business_month VARCHAR(6),pair_key VARCHAR(500),
            pdf_file_name VARCHAR(500),excel_file_name VARCHAR(500),original_pdf_path TEXT,original_excel_path TEXT,
            final_pdf_path TEXT,final_excel_path TEXT,pdf_sha256 VARCHAR(64),excel_sha256 VARCHAR(64),
            pdf_raw_text TEXT,excel_raw_json TEXT,raw_customer_name VARCHAR(500),system_customer_code VARCHAR(255),
            system_customer_name VARCHAR(500),customer_match_status VARCHAR(32),compare_status VARCHAR(32),
            exception_codes TEXT,exception_details TEXT,pdf_total_amount VARCHAR(64),excel_total_amount VARCHAR(64),
            review_status VARCHAR(32),created_at VARCHAR(64))"""))
        db.execute(text("""CREATE TABLE IF NOT EXISTS tlc_request_review_queue(
            id VARCHAR(64) PRIMARY KEY,batch_id VARCHAR(64),item_id VARCHAR(64) UNIQUE,business_month VARCHAR(6),
            pair_key VARCHAR(500),review_status VARCHAR(32),compare_status VARCHAR(32),raw_customer_name VARCHAR(500),
            system_customer_code VARCHAR(255),system_customer_name VARCHAR(500),exception_codes TEXT,created_at VARCHAR(64))"""))
        db.execute(text("DELETE FROM tlc_request_review_queue"))
        db.execute(text("DELETE FROM tlc_request_batch_compare_item"))
        db.execute(text("""INSERT INTO tlc_request_batch_compare_item(
            id,batch_id,business_month,pair_key,pdf_file_name,excel_file_name,
            original_pdf_path,original_excel_path,final_pdf_path,final_excel_path,
            pdf_sha256,excel_sha256,pdf_raw_text,excel_raw_json,raw_customer_name,
            system_customer_code,system_customer_name,customer_match_status,compare_status,
            exception_codes,exception_details,pdf_total_amount,excel_total_amount,review_status,created_at
        ) VALUES(
            'i1','b1','202601','abc','a.pdf','a.xlsx','c:/incoming/a.pdf','c:/incoming/a.xlsx',
            'c:/a.pdf','c:/a.xlsx','p','x','pdf raw','{}','株式会社ABC','','','UNMATCHED',
            'EXCEPTION','TOTAL_AMOUNT_MISMATCH','amount mismatch','100','90','WAIT_REVIEW','2026-01-01'
        )"""))
        db.execute(text("""INSERT INTO tlc_request_review_queue(
            id,batch_id,item_id,business_month,pair_key,review_status,compare_status,
            raw_customer_name,system_customer_code,system_customer_name,exception_codes,created_at
        ) VALUES(
            'r1','b1','i1','202601','abc','WAIT_REVIEW','EXCEPTION','株式会社ABC','','',
            'TOTAL_AMOUNT_MISMATCH','2026-01-01'
        )"""))
        db.commit()
        ensure_review_tables(db)
    finally:
        db.close()

def test_page_and_count():
    seed()
    response = client.get('/request-review-center')
    assert response.status_code == 200
    assert '请求书 Review' in response.text
    assert '/api/tlc-request-reviews' in response.text
    count = client.get('/api/tlc-request-reviews/wait-count')
    assert count.status_code == 200
    assert count.json()['count'] == 1

def test_force_review_requires_comment_and_updates_count():
    seed()
    rejected = client.put('/api/tlc-request-reviews/r1', json={
        'review_status':'REVIEWED_OK','operator':'tester','forced':True,'comment':''})
    assert rejected.status_code == 400
    accepted = client.put('/api/tlc-request-reviews/r1', json={
        'review_status':'REVIEWED_OK','operator':'tester','forced':True,'comment':'special approval'})
    assert accepted.status_code == 200
    assert accepted.json()['review_status'] == 'REVIEWED_OK'
    assert client.get('/api/tlc-request-reviews/wait-count').json()['count'] == 0

def test_dashboard_entry():
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "TLC_REQUEST_REVIEW_WORK_QUEUE_S04R1" in response.text
    assert "/request-review-center" in response.text
    assert "/api/tlc-request-reviews/wait-count" in response.text
    assert "MutationObserver" in response.text

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.db.session import get_db
from src.main import app
from src.services.request_review_service import ensure_review_tables


TEST_DB = Path(__file__).with_name(".test_build037_s04_request_review_dashboard.sqlite3")
ENGINE = create_engine(
    f"sqlite:///{TEST_DB.as_posix()}",
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=ENGINE,
)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_database():
    if TEST_DB.exists():
        TEST_DB.unlink()
    yield
    ENGINE.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()


def seed():
    db = TestSessionLocal()
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
        db.execute(text("""INSERT INTO tlc_request_batch_compare_item(
            id,batch_id,business_month,pair_key,pdf_file_name,excel_file_name,
            original_pdf_path,original_excel_path,final_pdf_path,final_excel_path,
            pdf_sha256,excel_sha256,pdf_raw_text,excel_raw_json,raw_customer_name,
            system_customer_code,system_customer_name,customer_match_status,compare_status,
            exception_codes,exception_details,pdf_total_amount,excel_total_amount,review_status,created_at
        ) VALUES(
            'test-i1','test-b1','209901','test-abc','test-a.pdf','test-a.xlsx',
            'c:/test/incoming/a.pdf','c:/test/incoming/a.xlsx',
            'c:/test/a.pdf','c:/test/a.xlsx','test-p','test-x','test pdf raw','{}',
            'TEST株式会社ABC','','','UNMATCHED','EXCEPTION','TOTAL_AMOUNT_MISMATCH',
            'test amount mismatch','100','90','WAIT_REVIEW','2099-01-01'
        )"""))
        db.execute(text("""INSERT INTO tlc_request_review_queue(
            id,batch_id,item_id,business_month,pair_key,review_status,compare_status,
            raw_customer_name,system_customer_code,system_customer_name,exception_codes,created_at
        ) VALUES(
            'test-r1','test-b1','test-i1','209901','test-abc','WAIT_REVIEW','EXCEPTION',
            'TEST株式会社ABC','','','TOTAL_AMOUNT_MISMATCH','2099-01-01'
        )"""))
        db.commit()
        ensure_review_tables(db)
    finally:
        db.close()


def test_page_and_count():
    seed()
    response = client.get("/request-review-center")
    assert response.status_code == 200
    assert "请求书 Review" in response.text
    assert "/api/tlc-request-reviews" in response.text

    count = client.get("/api/tlc-request-reviews/wait-count")
    assert count.status_code == 200
    assert count.json()["count"] == 1


def test_force_review_requires_comment_and_updates_count():
    seed()

    rejected = client.put(
        "/api/tlc-request-reviews/test-r1",
        json={
            "review_status": "REVIEWED_OK",
            "operator": "tester",
            "forced": True,
            "comment": "",
        },
    )
    assert rejected.status_code == 400

    accepted = client.put(
        "/api/tlc-request-reviews/test-r1",
        json={
            "review_status": "REVIEWED_OK",
            "operator": "tester",
            "forced": True,
            "comment": "special approval",
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["review_status"] == "REVIEWED_OK"
    assert client.get("/api/tlc-request-reviews/wait-count").json()["count"] == 0


def test_dashboard_entry():
    page = client.get("/dashboard")
    assert page.status_code == 200

    summary = client.get("/api/dashboard/summary")
    assert summary.status_code == 200, summary.text
    body = summary.json()

    request_todos = [
        item
        for item in body["todos"]
        if item["title"] == "待核对请求书"
    ]
    assert len(request_todos) == 1
    request_todo = request_todos[0]
    assert request_todo["href"] == "/request-review-center"
    assert isinstance(request_todo["count"], int)
    assert "TLC_REQUEST_REVIEW_WORK_QUEUE_S04R1" not in page.text
    assert "TLC_REQUEST_REVIEW_DASHBOARD_PATCH_V3" not in page.text

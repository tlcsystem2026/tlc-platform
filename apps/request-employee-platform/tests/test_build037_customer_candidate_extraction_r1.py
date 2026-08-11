from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import src.services.tlc_customer_candidate_service as candidate_service
from src.services.tlc_customer_candidate_service import (
    bulk_resolve_candidates,
    list_candidates,
    normalize_candidate_name,
    resolve_candidate,
    run_extraction,
)
from src.services.tlc_customer_master_service import ensure_customer_master_table, save_customer

ROOT = Path(__file__).parents[1]


def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'candidate.db'}")
    session = sessionmaker(bind=engine)()
    ensure_customer_master_table(session)
    return session


def test_normalization_removes_only_recipient_honorific():
    assert normalize_candidate_name(" 株式会社ABC　御中 ") == "株式会社ABC"
    assert normalize_candidate_name("合同会社XYZ") == "合同会社XYZ"
    assert normalize_candidate_name("(株)ABC 御中") == "株式会社ABC"
    assert normalize_candidate_name("（株）ABC") == "株式会社ABC"
    assert normalize_candidate_name("㈱ABC") == "株式会社ABC"
    assert normalize_candidate_name("株)ABC") == "株式会社ABC"
    assert normalize_candidate_name("(株ABC") == "株式会社ABC"
    assert normalize_candidate_name("（株ABC") == "株式会社ABC"


def test_preimport_file_batch_matches_and_creates_customer(tmp_path, monkeypatch):
    db = database(tmp_path)
    incoming = tmp_path / "Incoming" / "202607"
    incoming.mkdir(parents=True)
    (incoming / "request-1.pdf").write_bytes(b"pdf")
    (incoming / "request-1.xlsx").write_bytes(b"xlsx")
    (incoming / "request-2.xlsx").write_bytes(b"xlsx")
    monkeypatch.setattr(candidate_service, "standard_directories", lambda: {"incoming": tmp_path / "Incoming"})
    monkeypatch.setattr(candidate_service, "_extract_pdf", lambda path: "さばいさばいストア 御中")
    monkeypatch.setattr(candidate_service, "_extract_excel", lambda path: {
        "sheets": [{"title": "請求書", "rows": [["株式会社既存", "御中"]]}]
    })
    existing = save_customer(db, {"customer_id": "CUST-EXIST", "formal_name": "株式会社既存"})

    batch = run_extraction(db, "202607", operator="tester")
    assert batch["source_rows"] == 2
    assert batch["candidate_count"] == 2
    assert batch["matched_count"] == 1
    assert batch["review_count"] == 1

    rows = list_candidates(db, batch_id=batch["id"], limit=100)
    saba = next(row for row in rows if row["suggested_formal_name"] == "さばいさばいストア")
    known = next(row for row in rows if row["suggested_formal_name"] == "株式会社既存")
    assert saba["source_count"] == 1
    assert "request-1.pdf" in saba["source_pair_keys"]
    assert saba["review_status"] == "WAIT_REVIEW"
    assert known["review_status"] == "MATCHED"
    assert known["matched_customer_id"] == existing["id"]

    held = bulk_resolve_candidates(db, [saba["id"], "MISSING"], "HOLD", "tester", "later")
    assert held["requested"] == 2
    assert held["succeeded"] == 1
    assert held["failed"] == 1
    assert list_candidates(db, batch_id=batch["id"], status="ON_HOLD")[0]["id"] == saba["id"]

    resolved = resolve_candidate(db, saba["id"], "CREATE_NEW", "tester",
                                 customer_id="CUST-SABA", formal_name="さばいさばいストア")
    assert resolved["review_status"] == "IMPORTED"
    customer = db.execute(text("SELECT formal_name FROM tlc_customer_master WHERE customer_id='CUST-SABA'")).scalar_one()
    assert customer == "さばいさばいストア"


def test_page_and_routing_contracts():
    page = (ROOT / "src/web/static/customer_import_candidate_center.html").read_text(encoding="utf-8")
    main = (ROOT / "src/main.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "src/web/static/dashboard.html").read_text(encoding="utf-8")
    permissions = (ROOT / "src/services/tlc_api_permission_service.py").read_text(encoding="utf-8")
    assert "TLC_CUSTOMER_CANDIDATE_BULK_REVIEW_R1" in page
    assert "Incoming/YYYYMM" in page
    assert "来源请求书 Batch" not in page
    assert "批量创建客户" in page
    assert "导入审核结果 CSV" in page
    assert "不会自动创建、关联或删除客户" in page
    assert "formal-name-input{width:380px" in page
    assert "/api/customer-candidates/bulk-resolve" in page
    assert "tlc_customer_candidate_router" in main
    assert "/customer-import-candidate-center" in dashboard
    assert "CUSTOMER_CANDIDATE" in permissions
    modules = (ROOT / "src/services/tlc_access_control_service.py").read_text(encoding="utf-8")
    assert '("CUSTOMER_CANDIDATE","客户候选提取与审核")' in modules
